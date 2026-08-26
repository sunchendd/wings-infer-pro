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
- files:scheme 可声明待生成的配置文件({name, content}),由 plan_scheme_files
    填占位符后作为计划交给 wings-control 写入(任意文本:YAML/JSON/conf)。

合并:
- deep_merge_dicts:合并【未渲染】的 cli_params(dict 级深合并),用于同一特性内
  多 scheme 合并(如 kv_offload 的 cpu+disk 都带 kv_transfer_config,需深合并后再渲染)。
- merge_engine_params:合并【已渲染】的 EngineParams(env update + engine_config 合并),
  供上层 merge(open_source_template(), smart_accel()) 使用。
"""

import ast
import logging
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from wings_accel.schemas import (
    EngineParams,
    GeneratedFile,
    SmartAccelConfigurationError,
    _FeatureOutput,
)

logger = logging.getLogger(__name__)

# 匹配 {placeholder} 形态的占位符令牌(用于配置文件 content 的子串替换)。
_TOKEN_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")

# 匹配写盘内容里的 ${VAR}(运行时 envsubst 展开),用于检测 files 是否需要 envsubst 步骤。
_RUNTIME_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

# 匹配 {= expr} 算术求值标记(body 不含花括号,禁止与 {name} 占位符嵌套;与 _TOKEN_RE 不相交)。
_EXPR_RE = re.compile(r"\{=\s*([^{}]*)\}")

# {= expr} 允许的二元算术运算符(ast 节点类型 → Python 运算);其余节点一律拒(见 _eval_arith)。
_EXPR_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}


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
    # ── KV 存储后端(memcache / mooncake)渲染参数 ──
    # 工具选择由 yaml 声明 + offload 按 kv_connector 内容路由(不再有 KV_STORE_BACKEND env)。
    # IP 用 {rank_ip}/{master_ip} → ${RANK_IP}/${MASTER_IP},运行时 envsubst 展开。
    gpu_count: int = 1 # 卡数(= device_count);mooncake global_segment_size / memcache dram.size 按卡均分用
    tp_size: int = 0 # 张量并行度;lmcache {lookup_server_worker_ids} → "0,..,tp_size-1"
    dp_size: int = 0 # 数据并行度;对齐 tp_size,供 {= expr } 算术用(如 per-pod 段大小派生)
    config_root: str = "" # smart-accel 根目录;files 条目 src 解析基准(_resolve_smart_accel_root 结果)
    source_file: str = "" # 实际命中的 SmartAccel YAML 文件,供生成文件审计使用
    source_path: str = "" # 已路由的 YAML 路径前缀,供生成文件审计使用


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
    # ── KV 存储后端(memcache/mooncake)占位符 ──
    # {rank_ip}/{master_ip}:per-node/master IP。resolve 期写成 ${VAR} 字面量,
    # 运行时由 offload 生成的 envsubst 步骤展开(engine 容器 RANK_IP/MASTER_IP 由拓扑注入)。
    if token == "{rank_ip}":
        return "${RANK_IP}"
    if token == "{master_ip}":
        return "${MASTER_IP}"
    if token == "{lookup_server_worker_ids}":
        # lmcache lookup server worker ids:tp_size=N → "0,1,...,N-1"(仅 lmcache disk/cpu_disk scheme 用)。
        return ",".join(str(i) for i in range(ctx.tp_size)) if ctx.tp_size > 0 else None
    return None


# ───────────────────────────────────────────────
# {= expr} 算术求值(content / cli_params / envs 通用;与 {name} 占位符正则不相交)
# ───────────────────────────────────────────────

def _expr_namespace(ctx: PlaceholderContext) -> Dict[str, int]:
    """``{= expr}`` 求值命名空间:PlaceholderContext 的数值字段(算术只对数字有意义)。

    覆盖真实派生用例:per-card 容量 = ``memory_capacity_gb // gpu_count``、
    ``tp_size * <n>`` 等。新增数值字段时在此登记即可暴露给 expr。
    """
    return {
        "memory_capacity_gb": ctx.memory_capacity_gb,
        "disk_capacity_gb": ctx.disk_capacity_gb,
        "qat_device_count": ctx.qat_device_count,
        "qat_compression_level": ctx.qat_compression_level,
        "gpu_count": ctx.gpu_count,
        "tp_size": ctx.tp_size,
        "dp_size": ctx.dp_size,
    }


def _eval_arith(node: ast.AST, ns: Dict[str, int]) -> Any:
    """白名单递归求值:仅允许 ``+ - * / // % **``、一元正负、数字常量、命名引用。

    Call / Attribute / Subscript / Compare / BoolOp / Lambda 等**一律拒**(抛 ValueError)→
    调用方据此保留 ``{= ...}`` 字面量。**不使用 eval()**,仅 ast 白名单递归。
    """
    if isinstance(node, ast.Expression):
        return _eval_arith(node.body, ns)
    if isinstance(node, ast.Constant):
        # bool 是 int 子类,显式拒(避免 {= True} 这类怪异写法);只收 int/float。
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"非数字常量: {node.value!r}")
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in ns:
            raise ValueError(f"未知变量: {node.id}")
        return ns[node.id]
    if isinstance(node, ast.BinOp):
        op = _EXPR_BINOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op(_eval_arith(node.left, ns), _eval_arith(node.right, ns))
    if isinstance(node, ast.UnaryOp):
        operand = _eval_arith(node.operand, ns)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
    raise ValueError(f"不支持的语法: {type(node).__name__}")


def _format_expr_result(value: Any) -> str:
    """格式化求值结果:整值浮点 → 整数(``8/2``→``'4'`` 而非 ``'4.0'``);否则 str。"""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _eval_expr_substr(text: str, ctx: PlaceholderContext) -> str:
    """子串替换文本里的 ``{= expr}`` 算术标记为求值结果。

    与 ``{name}`` 占位符正则不相交(``{=`` vs ``{字母``)。expr 解析/求值失败(语法错、未知变量、
    非白名单节点如函数调用、除零)→ **原样保留 ``{= ...}`` 字面量**(与 ``_resolve_token`` 返回
    None→保留语义一致),仅 debug 日志(常见于故意保留的写法,避免 warn 噪音)。
    """
    ns = _expr_namespace(ctx)

    def _sub(match: "re.Match[str]") -> str:
        body = match.group(1).strip()
        if not body:
            return match.group(0)
        try:
            tree = ast.parse(body, mode="eval")
            return _format_expr_result(_eval_arith(tree, ns))
        except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as exc:
            logger.debug("smart_accel: failed to evaluate {= expr}; preserving literal %r: %s", match.group(0), exc)
            return match.group(0)

    return _EXPR_RE.sub(_sub, text)


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
    return _eval_expr_substr(out, ctx)


def _fill_str_substr(value: str, ctx: PlaceholderContext) -> str:
    """多行文本里的 {占位符} 子串替换(配置文件 content 用)。

    与 ``_fill_str`` 的整值精确匹配不同,本函数把文本里**每个** ``{placeholder}`` 出现处都替换为
    ``_resolve_token`` 的解析值;未识别 / 条件未满足的占位符原样保留。``$path`` / ``$draft_model_path``
    同样子串替换。用于 files 块的 content(任意文本:YAML/JSON/conf),使文件计划内容的占位符全部填实。

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
    return _eval_expr_substr(out, ctx)


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


def _resolve_file_entry(
    f: Dict[str, Any],
    ctx: PlaceholderContext,
    volume: Path,
) -> Optional[Dict[str, Any]]:
    """解析单个 files 条目为 {path, content, scope, mode}。

    - ``path``:优先(容器内路径);缺省取 ``name``(向后兼容 → ``<volume>/<name>``)。
      以 ``/`` 开头按绝对路径;否则相对 ``volume``。
    - ``src`` / ``content`` 二选一:``src`` 从 ``ctx.config_root`` 读模板文件;``content`` 内联。
    - ``scope``(all/master/client,默认 all)、``mode``(权限如 ``"0755"``)透传,供 offload 合成 pre_serve。

    返回 None 表示条目无效(非 dict / 缺 path 与 name)。src 路径问题属于配置错误，直接抛出。
    """
    if not isinstance(f, dict):
        return None
    path_raw = f.get("path") or f.get("name")
    if not path_raw:
        return None
    p = str(path_raw)
    path = Path(p) if p.startswith("/") else (volume / p)
    src = f.get("src")
    if src:
        if not ctx.config_root:
            raise SmartAccelConfigurationError(
                f"SmartAccel files src requires config_root: {src!r}"
            )
        raw_src_path = Path(str(src))
        if raw_src_path.is_absolute():
            raise SmartAccelConfigurationError(
                f"SmartAccel files src must be relative to config_root: {src!r}"
            )
        try:
            source_root = Path(ctx.config_root).resolve()
            src_path = (source_root / raw_src_path).resolve()
        except (OSError, RuntimeError) as exc:
            raise SmartAccelConfigurationError(
                f"Failed to resolve SmartAccel files src: {src!r}"
            ) from exc
        if not src_path.is_relative_to(source_root):
            raise SmartAccelConfigurationError(
                f"SmartAccel files src escapes config_root: {src!r}"
            )
        if not src_path.is_file():
            raise SmartAccelConfigurationError(
                f"SmartAccel files src is not a readable file: {src!r}"
            )
        try:
            content: Any = src_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SmartAccelConfigurationError(
                f"Failed to read SmartAccel files src: {src!r}"
            ) from exc
    else:
        content = f.get("content", "")
    scope = str(f.get("scope") or "all").strip().lower()
    if scope not in ("all", "master", "client"):
        scope = "all"
    return {
        "path": str(path),
        "content": content,
        "scope": scope,
        "mode": f.get("mode"),
    }


def plan_scheme_files(
    files: Optional[List[Dict[str, Any]]],
    ctx: PlaceholderContext,
    volume: Optional[str] = None,
    source_path_prefix: str = "",
) -> List[GeneratedFile]:
    """把 scheme 的 ``files:`` 块渲染为文件计划,不执行任何写盘操作。

    files 条目**自描述 schema**:
      - ``path``(必填,容器内路径;或 ``name`` 兼容 → ``<volume>/<name>``)
      - ``src``(相对 ``config_root`` 的模板文件)/ ``content``(内联)二选一
      - ``scope``(all/master/client)、``mode``(权限)透传给 offload

    content 支持与 cli_params/envs 相同的 ``{name}`` 占位符与 ``$path`` 令牌;``{rank_ip}``/``{master_ip}``
    解析为 ``${RANK_IP}``/``${MASTER_IP}`` 字面量,**运行时由 offload 生成的 envsubst 步骤展开**。

    Args:
        files: scheme 的 ``files`` 列表;``None``/空 → 返回 ``[]``(不建目录、不写盘)。
        ctx: 占位符上下文(填充 ``content`` 里的 ``{name}``/``$path``;``config_root`` 供 ``src`` 解析)。
        volume: 计划路径根目录;``None`` → 取 ``SHARED_VOLUME_PATH`` 环境变量,缺省 ``/shared-volume``。
        source_path_prefix: 选中 smart_accel 配置块的 YAML 路径前缀,用于 audit 溯源。

    Returns:
        ``GeneratedFile`` 列表(保持输入顺序,跳过无效条目)。每项的 ``content`` 已填充
        解析期占位符，``runtime_vars`` 是内容中检测到的 ``${VAR}`` 列表，供 offload
        合成运行时 envsubst 步骤。整体为空 → ``[]``。
    """
    if not files:
        return []
    vol = Path(volume or os.getenv("SHARED_VOLUME_PATH", "/shared-volume"))
    out: List[GeneratedFile] = []
    for file_index, f in enumerate(files):
        entry = _resolve_file_entry(f, ctx, vol)
        if entry is None:
            continue
        content = entry["content"]
        # content 是任意文本(YAML/JSON/conf):子串替换填占位符(整值匹配填不了多行文本)。
        filled = _fill_str_substr(content, ctx) if isinstance(content, str) else content
        text = "" if filled is None else str(filled)
        mode = entry.get("mode")
        runtime_vars = sorted(set(_RUNTIME_VAR_RE.findall(text)))
        source_path = (
            f"{source_path_prefix}.files[{file_index}]"
            if source_path_prefix
            else ""
        )
        out.append(GeneratedFile(
            path=entry["path"],
            content=text,
            mode=mode,
            scope=entry["scope"],
            source_file=ctx.source_file,
            source_path=source_path,
            runtime_vars=runtime_vars,
        ))
        logger.info(
            "smart_accel: planned config file %s (runtime_vars=%s)",
            entry["path"], runtime_vars,
        )
    return out




def extract_packages(scheme: Dict[str, Any]) -> List[str]:
    """从单个 scheme dict 读 ``packages`` 依赖,统一返回 ``name:version`` 字符串列表。

    YAML 形态(**键值对**,name→version,每行一个;**无 list dash**):

        - name: suffix
          packages:
            arctic-inference: 0.1.1

    输出统一为 ``["name:version", ...]``(与 install.py manifest / 报错信息的
    ``name:version`` 风格一致;packages 经 ``--config '{json}'`` 传递,纯 JSON 字符串,
    无 shell/pip 解析歧义,无需 pip-style ``==``)。
    兼容旧 list 形态与单字符串(原样保留)。

    Args:
        scheme: 单个 scheme dict;``packages`` 缺失 → 返回空列表。

    Returns:
        ``name:version`` 字符串列表(保留输入顺序);空键/空串丢弃。
    """
    raw = (scheme or {}).get("packages")
    if isinstance(raw, dict):
        return [f"{name}:{ver}" for name, ver in raw.items() if name]
    if isinstance(raw, list):
        out: List[str] = []
        for item in raw:
            if isinstance(item, dict):
                out.extend(f"{k}:{v}" for k, v in item.items() if k)
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


def render_pre_serve(
    commands: Optional[List[str]],
    ctx: PlaceholderContext,
) -> List[str]:
    """渲染已有 pre-serve 命令列表的兼容工具：填 ``{占位符}``(子串替换)。

    当前 SmartAccel YAML 不读取 ``pre_serve`` 相关字段；KV 存储后端的启动前
    命令由 ``files:`` 计划自动合成。本函数仅保留给已有 Python 调用方使用。

    与 files content 同走 ``_fill_str_substr``:``{rank_ip}``/``{master_ip}`` 等占位符按 ctx 填实;
    ``$local_ip`` / ``$node0_ip`` / ``${RANK_IP}`` 等 wings-control 拓扑占位与 shell 变量**原样保留**
    (本函数只认 ``{}`` 与 ``$path``,不碰 ``$local_ip``),交 ``topology_inject`` 在注入期替换。

    Args:
        commands: scheme 的 ``pre_serve`` / ``pre_serve_master`` 命令字符串列表;``None``/空 → ``[]``。
        ctx: 占位符上下文。

    Returns:
        渲染后的命令列表(保持顺序);非字符串元素丢弃。
    """
    if not commands:
        return []
    return [_fill_str_substr(cmd, ctx) for cmd in commands if isinstance(cmd, str)]


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
