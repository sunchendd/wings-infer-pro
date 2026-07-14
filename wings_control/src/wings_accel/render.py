"""渲染层 — 把 YAML 的 cli_params / envs 渲染成引擎 CLI 结构与环境变量。

这是 smart_accel 数据驱动扩展性的核心:YAML 里任意键值对都能被表达成引擎参数,
无需在 Python 里为每个 flag 写专门代码。

重要关键点:
- cli_params 顶层键保持 snake_case,嵌套 dict/list 原样保留。
- 本层只填充占位符并保留结构化 dict;最终 argv 渲染由 wings-control 完成。
- 占位符只替换字符串值;未知占位符保留字面量,便于兼容旧配置。
- deep_merge_dicts 处理未渲染 dict,merge_engine_params 处理已渲染 EngineParams,两者语义不同。

渲染规则:
- cli_params 填充占位符后直接作为结构化 engine_config 输出。
- bool / scalar / dict / list 均保留原类型;最终 argv 由 wings-control 渲染。
- 占位符:cli_params / envs 的字符串值支持 {name} 占位符与 $path 令牌,
  由 PlaceholderContext 解析(见 _fill_str)。
- files:scheme 可声明要落盘的配置文件({name, content}),由 write_scheme_files
  填占位符后写到 SHARED_VOLUME_PATH/<name>(任意文本:YAML/JSON/conf)。

合并:
- deep_merge_dicts:合并【未渲染】的 cli_params(dict 级深合并),用于同一特性内
  多 scheme 合并(如 kv_offload 的 cpu+disk 都带 kv_transfer_config,需深合并后再渲染)。
- merge_engine_params:合并【已渲染】的 EngineParams(env update + engine_config 合并),
  供上层 merge(open_source_template(), smart_accel()) 使用。
"""

import logging
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from wings_accel.schemas import EngineParams, _FeatureOutput

logger = logging.getLogger(__name__)

# 匹配 {placeholder} 形态的占位符令牌(用于配置文件 content 的子串替换)。
_TOKEN_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")


@dataclass
class PlaceholderContext:
    """占位符解析上下文 — 各 expander 从 SmartAccelInput 各子配置派生。"""

    # KV offload 容量 / 介质(来自 SmartKVCacheConfig)
    memory_capacity_gb: int = 0
    memory_offload_enabled: bool = False
    disk_capacity_gb: int = 0
    disk_offload_enabled: bool = False
    disk_path: str = ""
    qat_enabled: bool = False
    qat_device_count: int = 0
    qat_compression_level: int = 0
    # 投机解码草稿模型路径(来自 SmartDecodingConfig.model_path),解析 $path 令牌
    draft_model_path: str = ""


# ───────────────────────────────────────────────
# 占位符填充
# ───────────────────────────────────────────────

def _resolve_token(token: str, ctx: PlaceholderContext) -> Optional[str]:
    """解析单个 ``{placeholder}`` 令牌为字符串值;未识别 / 条件未满足返回 None。

    占位符解析的**单一判定点**:``_fill_str``(整值精确匹配,供 cli_params/envs)与
    ``_fill_str_substr``(子串替换,供 files content)都走本函数,杜绝两处各判一次。

    - 返回 None 表示「原样保留字面量令牌」(如 ``{disk_path}`` 在 disk 未启用时)。
    - ``{mem_gb_to_blocks}`` / ``{mem_gb_to_bytes}`` 恒有返回值(未启用 → "0")。
    - ``{qat_device_count}`` / ``{qat_compression_level}`` 恒渲染数值(与历史 native 行为一致;
      qat 段 enabled:false 时也保留数值,使 lmcache_config.yaml 始终合法)。这两个令牌仅在
      配置文件 content 中使用,不进 cli_params/envs。

    Args:
        token: 形如 ``"{disk_path}"`` 的占位符令牌(含花括号)。
        ctx: 占位符上下文。

    Returns:
        解析后的字符串值;未识别 / 条件未满足 → None(调用方保留字面量)。
    """
    if token == "{memory_capacity_gb}":
        return str(ctx.memory_capacity_gb) if ctx.memory_offload_enabled else None
    if token == "{disk_capacity_gb}":
        return str(ctx.disk_capacity_gb) if ctx.disk_offload_enabled else None
    if token == "{disk_path}":
        return ctx.disk_path if ctx.disk_offload_enabled else None
    if token == "{mem_gb_to_blocks}":
        # NPU(vllm-ascend)KV 卸载用 num_cpu_blocks(块数);GiB → 块(每块 16 KiB)。
        if ctx.memory_offload_enabled and ctx.memory_capacity_gb > 0:
            return str(int((ctx.memory_capacity_gb * 1024) // 16))
        return "0"
    if token == "{mem_gb_to_bytes}":
        # 原生 vLLM(CUDA)≥v0.14 KV 卸载用 cpu_bytes_to_use(字节,全 TP 合计);
        # 它静默忽略 num_cpu_blocks,故 CUDA 配置必须用本占位符产字节。GiB → 字节。
        if ctx.memory_offload_enabled and ctx.memory_capacity_gb > 0:
            return str(int(ctx.memory_capacity_gb) * 1024 * 1024 * 1024)
        return "0"
    if token == "{cpu_swap_space_gb}":
        # M_swap = 0:启动设 swap_space=0(无 beam search 前提),不再吃 offload 容量
        return "0" if ctx.memory_offload_enabled else None
    if token == "{qat_enabled}":
        return "true" if ctx.qat_enabled else "false"
    if token == "{qat_device_count}":
        return str(ctx.qat_device_count)
    if token == "{qat_compression_level}":
        return str(ctx.qat_compression_level)
    return None


def _fill_str(value: str, ctx: PlaceholderContext) -> str:
    """填充单个字符串值里的 {name} 占位符与 $path 令牌(整值精确匹配)。

    供 cli_params / envs:整值等于某 ``{placeholder}`` 才替换,未命中原样返回
    (保留 {xxx} 字面量,与历史行为一致)。多行文本里的 {占位符} 子串替换见 ``_fill_str_substr``。

    Args:
        value: 待填充的字符串(典型为单个占位符或纯字面量)。
        ctx: 占位符上下文。

    Returns:
        填充后的字符串;未命中占位符时原样返回。
    """
    # $path 令牌(草稿模型路径):整值命中
    if value in ("$path", "$draft_model_path"):
        return ctx.draft_model_path

    resolved = _resolve_token(value, ctx)
    if resolved is not None:
        return resolved

    # $path 子串替换(嵌在更大的字符串里)
    out = value
    if "$path" in out:
        out = out.replace("$path", ctx.draft_model_path)
    if "$draft_model_path" in out:
        out = out.replace("$draft_model_path", ctx.draft_model_path)
    return out


def _fill_str_substr(value: str, ctx: PlaceholderContext) -> str:
    """多行文本里的 {占位符} 子串替换(配置文件 content 用)。

    与 ``_fill_str`` 的整值精确匹配不同,本函数把文本里**每个** ``{placeholder}`` 出现处都替换为
    ``_resolve_token`` 的解析值;未识别 / 条件未满足的占位符原样保留。``$path`` / ``$draft_model_path``
    同样子串替换。用于 files 块的 content(任意文本:YAML/JSON/conf),使落盘配置文件的占位符全部填实。

    Args:
        value: 配置文件文本(可能含多个 {占位符} 子串)。
        ctx: 占位符上下文。

    Returns:
        占位符全部填充后的文本;未识别占位符保留字面量。
    """
    def _sub(match: re.Match) -> str:
        resolved = _resolve_token(match.group(0), ctx)
        return resolved if resolved is not None else match.group(0)

    out = _TOKEN_RE.sub(_sub, value)
    if "$path" in out:
        out = out.replace("$path", ctx.draft_model_path)
    if "$draft_model_path" in out:
        out = out.replace("$draft_model_path", ctx.draft_model_path)
    return out


def fill_placeholders(node: Any, ctx: PlaceholderContext) -> Any:
    """递归填充 dict / list / str 里的占位符;非字符串原样返回。"""
    if isinstance(node, str):
        return _fill_str(node, ctx)
    if isinstance(node, dict):
        return {k: fill_placeholders(v, ctx) for k, v in node.items()}
    if isinstance(node, list):
        return [fill_placeholders(v, ctx) for v in node]
    return node


def fill_envs(envs: Dict[str, Any], ctx: PlaceholderContext) -> Dict[str, str]:
    """填充 envs 的占位符,值统一 stringify(env 值必须是字符串)。"""
    result: Dict[str, str] = {}
    for k, v in (envs or {}).items():
        filled = fill_placeholders(v, ctx)
        result[str(k)] = filled if isinstance(filled, str) else str(filled)
    return result


def render_engine_config(cli_params: Dict[str, Any], ctx: PlaceholderContext) -> Dict[str, Any]:
    """把 YAML cli_params 填充占位符后保留为结构化 engine_config。"""
    filled = fill_placeholders(cli_params or {}, ctx)
    return dict(filled or {})


def write_scheme_files(
    files: Optional[List[Dict[str, Any]]],
    ctx: PlaceholderContext,
    volume: Optional[str] = None,
) -> List[str]:
    """把 scheme 的 ``files:`` 块渲染(填占位符)并写到共享卷。

    通用配置文件落盘:``files`` 形如 ``[{"name": <filename>, "content": <text>}, ...]``,
    ``content`` 为任意文本(YAML/JSON/conf),支持与 cli_params/envs 相同的 ``{name}`` 占位符
    与 ``$path`` 令牌,未知占位符原样保留。每个文件写到 ``<volume>/<name>``。

    用途:lmcache_config.yaml / mooncake.json / mmc_local.conf 等任意配置文件统一由本函数
    落盘,无需为每种配置写专门代码。env 变量指向写出的文件由 scheme 的 ``envs:`` 字面量声明。

    Args:
        files: scheme 的 ``files`` 列表;``None`` / 空 → 返回空列表(不创建目录、不写盘);
            元素非 dict 或缺 ``name`` → 跳过该元素。
        ctx: 占位符上下文(填充 ``content`` 里的 ``{name}`` / ``$path``)。
        volume: 写盘根目录;``None`` → 取 ``SHARED_VOLUME_PATH`` 环境变量,缺省 ``/shared-volume``。

    Returns:
        已写文件的绝对路径列表(保持输入顺序);整体为空时返回 ``[]``。

    Raises:
        OSError: 创建目录或写文件失败时由文件系统抛出。
    """
    if not files:
        return []
    root = Path(volume or os.getenv("SHARED_VOLUME_PATH", "/shared-volume"))
    root.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for f in files:
        if not isinstance(f, dict) or not f.get("name"):
            continue
        content = f.get("content", "")
        # content 是任意文本(YAML/JSON/conf):用子串替换填占位符(整值匹配填不了多行文本)。
        filled = _fill_str_substr(content, ctx) if isinstance(content, str) else content
        path = root / str(f["name"])
        path.write_text("" if filled is None else str(filled), encoding="utf-8")
        written.append(str(path))
        logger.info("smart_accel: wrote config file %s", path)
    return written


def extract_packages(scheme: Dict[str, Any]) -> List[str]:
    """从单个 scheme dict 读 ``packages`` 依赖,统一返回 pip-style ``name==version`` 字符串列表。

    YAML 形态(**键值对**,name→version,每行一个;**无 list dash**):

        - name: suffix
          packages:
            arctic-inference: 0.1.1

    输出统一为 ``["name==version", ...]``(pip 安装 specifier,供 install 段 ``--config`` 的 packages)。
    兼容旧 list 形态与单字符串(原样保留)。

    Args:
        scheme: 单个 scheme dict;``packages`` 缺失 → 返回空列表。

    Returns:
        ``name==version`` 字符串列表(保留输入顺序);空键/空串丢弃。
    """
    raw = (scheme or {}).get("packages")
    if isinstance(raw, dict):
        return [f"{name}=={ver}" for name, ver in raw.items() if name]
    if isinstance(raw, list):
        out: List[str] = []
        for item in raw:
            if isinstance(item, dict):
                out.extend(f"{k}=={v}" for k, v in item.items() if k)
            elif item is not None and str(item) != "":
                out.append(str(item))
        return out
    if isinstance(raw, str) and raw:
        return [raw]
    return []


def render_scheme(
    scheme: Dict[str, Any],
    ctx: PlaceholderContext,
    degraded: bool = False,
    degrade_reason: str = "",
) -> _FeatureOutput:
    """把单个 scheme dict(name + cli_params + envs + packages)渲染成 _FeatureOutput。

    各 expander 选定 scheme 后统一调用本函数,保证渲染规则只有一处。
    """
    scheme = scheme or {}
    return _FeatureOutput(
        scheme=str(scheme.get("name", "")),
        engine_params=EngineParams(
            env=fill_envs(scheme.get("envs") or {}, ctx),
            engine_config=render_engine_config(scheme.get("cli_params") or {}, ctx),
        ),
        degraded=degraded,
        degrade_reason=degrade_reason,
        packages=extract_packages(scheme),
    )


# ───────────────────────────────────────────────
# 合并
# ───────────────────────────────────────────────

def deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """深合并两个【未渲染】cli_params dict(原地改 base,返回 base)。

    - 嵌套 dict 递归合并(如 kv_transfer_config)
    - 标量 / list:last-write-wins(整体替换)
    用于同一特性多 scheme 合并(cpu+disk)后再一次性渲染。
    """
    for k, v in (override or {}).items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            base[k] = deep_merge_dicts(base[k], v)
        else:
            base[k] = v
    return base


def merge_engine_params(base: EngineParams, override: EngineParams) -> EngineParams:
    """合并两个 EngineParams:env 后者覆盖前者,engine_config 深合并。

    供上层 merge(open_source_template(), smart_accel()) 使用;返回新对象,不改入参。
    """
    engine_config = deepcopy(base.engine_config or {})
    engine_config = deep_merge_dicts(engine_config, deepcopy(override.engine_config or {}))
    return EngineParams(
        env={**(base.env or {}), **(override.env or {})},
        engine_config=engine_config,
    )
