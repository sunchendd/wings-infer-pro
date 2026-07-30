"""
YAML 加载器 — 从模型 YAML 构建 SmartAccelInput。

解析以下标签:
- model: 模型元数据(model_id / name / architecture)
- hardware_profile: 硬件配置(gpu_type / gpu_count)
- smart_accel: smart_accel 块本体(嵌入 SmartAccelInput.smart_accel 供 func_smart_accel 展开)
- scenarios.{topology}.strategies.{name}.engine_config: 引擎配置(读取 name/version/TP/DP,可选)

重要关键点:
- smart_accel 精确取自命中的模型 YAML,不合并 default_model.yaml。
- 自动探测只根据 smart_accel 子块决定默认开关;CLI/LoadFlags 可覆盖用户意图。
- KV offload 介质用 kv_offload[].name == cpu/disk 探测;主开关开但无介质时不兜底。
- 找不到 YAML 返回 None,由 api.resolve_smart_accel_from_config 调用方按 no-op 处理。
- config_root/smart-accel 优先,否则回落到随包分发的 smart-accel 配置。

智能内存分配(memory_offload_size_mode):
- auto: 从 scenarios engine_config 读取 TP/DP,结合 pod_available_memory_gb 估算 CPU 卸载容量。
- auto 估算低于 min_offload_threshold_gb 时默认关闭 memory_offload;显式开启则保留用户意图。
- 数值字符串:按 GB 固定配置。
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from wings_accel.memory_estimator import estimate_offload_memory
from wings_accel.schemas import (
    DeploymentMode,
    EngineConfig,
    ModelConfig,
    SmartAccelInput,
    SmartDecodingConfig,
    SmartKVCacheConfig,
    SmartKVSparseConfig,
    SystemConfig,
)

logger = logging.getLogger(__name__)

# 匹配运行时传入的版本,提取基础版本+预发布渠道,用于把构建版本归一化成渠道目录。
# 与 wings_ctl/engines/version_resolver.py 的 _REQUESTED_VERSION_RE 保持一致(自闭环,不反向依赖)。
# 示例:v0.21.0rc1-20260709144216 → base=0.21.0 + channel=rc → v0.21.0rc
_SMART_ACCEL_PRERELEASE_RE = re.compile(
    r"^v?(\d+\.\d+\.\d+)([A-Za-z]+)(?:\d+)?(?:[-+].*)?$"
)


def _candidate_version_dirs(engine_version: str) -> list[str]:
    """把传入的版本号展开成候选目录名列表(带 v 前缀),按精确优先排序。

    - "0.23.0"                        → ["v0.23.0"]
    - "v0.21.0rc"                     → ["v0.21.0rc"]
    - "v0.21.0rc1-20260709144216"     → ["v0.21.0rc1-20260709144216", "v0.21.0rc"]
    - "0.21.0rc1-20260709144216"      → ["v0.21.0rc1-20260709144216", "v0.21.0rc"]

    第一个候选 = 原样(精确匹配优先);若能归一化出渠道目录且与原样不同,追加为第二候选。
    """
    raw = str(engine_version).strip()
    if not raw:
        return []
    version_dir_name = raw if raw.startswith("v") else f"v{raw}"
    candidates = [version_dir_name]
    m = _SMART_ACCEL_PRERELEASE_RE.match(raw)
    if m:
        normalized = f"v{m.group(1)}{m.group(2)}"
        if normalized != version_dir_name:
            candidates.append(normalized)
    return candidates


@dataclass
class LoadFlags:
    """覆盖开关,所有字段都有默认值,不传也运行。

    MaaS 显式开关为唯一驱动:kv/sparse/decoding 是否启用 100% 由本类对应 flag 决定,
    smart_accel YAML 仅作全量占位模板(YAML 块存在不再自动启用任何特性)。KV memory
    介质另需 memory_offload_size_mode 为 auto 或数值字符串,且 YAML 需有 cpu scheme。
    """

    kv: bool = False
    sparse: bool = False
    disk: bool = False
    qat: bool = False
    disk_gb: int = 512
    disk_path: str = "/var/cache/lmcache"
    qat_devices: int = 2
    qat_level: int = 1
    decoding_enabled: bool = False
    decoding_model_path: str = ""
    sparse_level: str = "performance_first"
    pd_role: Optional[str] = None
    # KV_MEM_OFFLOAD_SIZE: "auto" 或数值字符串(GB);空字符串/false 表示不显式下发。
    memory_offload_size_mode: str = ""
    pod_available_memory_gb: int = 0
    min_offload_threshold_gb: int = 100


def _has_backend_scheme(kv_offload_block) -> bool:
    """kv_offload 块里是否存在后端 scheme(``kv_connector`` 为 ``AscendStoreConnector``[mooncake/memcache]
    或 ``LMCacheAscendConnectorV1Dynamic``[ascend lmcache,方法三])。

    工具选择按 connector 内容路由,不再靠 ``KV_STORE_BACKEND`` env。后端 scheme(name=cpu)命中即视为
    声明了内存卸载工具(cpu 介质下的实现,参与 has_memory_method)。与 ``offload._find_backend_scheme``
    同列。
    """
    if not isinstance(kv_offload_block, list):
        return False
    for s in kv_offload_block:
        if not isinstance(s, dict):
            continue
        kt = (s.get("cli_params") or {}).get("kv_transfer_config") or {}
        if (kt.get("kv_connector") or "") in ("AscendStoreConnector", "LMCacheAscendConnectorV1Dynamic"):
            return True
    return False


def load_smart_accel_from_yaml(
    yaml_path: str,
    flags: Optional[LoadFlags] = None,
) -> Optional[SmartAccelInput]:
    """读取 SmartAccel 模型 YAML,构造 SmartAccelInput。

    smart_accel 精确读取自 smart-accel model yaml 本身(不合并 default_model.yaml —— 需求1),
    嵌入 SmartAccelInput.smart_accel,func_smart_accel 直接消费,不再旁路 model_dict。
    kv_offload/decoding/sparse 等直接取自该 model yaml;缺失则对应特性不启用。

    Args:
        yaml_path: YAML 文件路径;缺失返回 None(上层按 no-op 处理)
        flags: 覆盖开关,缺省时使用 LoadFlags() 默认值

    Returns:
        SmartAccelInput: 聚合上下文 + 用户开关 + smart_accel 模板块;缺失时 None
    """
    if flags is None:
        flags = LoadFlags()

    path = Path(yaml_path)
    if not path.is_file():
        logger.warning("SmartAccel YAML not found: %s", path)
        return None

    with open(path) as f:
        model_dict = yaml.safe_load(f) or {}

    model = model_dict.get("model", {})
    hw = model_dict.get("hardware_profile", {})

    # 精确读取 smart-accel model yaml 的 smart_accel(不合并 default_model.yaml —— 需求1)
    smart_accel = model_dict.get("smart_accel", {}) or {}

    hardware_config = SystemConfig(
        gpu_type=hw.get("gpu_type", "A100"),
        gpu_count=hw.get("gpu_count", 1),
        pod_available_memory_gb=flags.pod_available_memory_gb,
    )

    model_config = ModelConfig(
        model_path=model.get("model_id", ""),
        model_name=model.get("name"),
        model_arch=model.get("architecture"),
    )

    chosen_ec = _get_chosen_engine_config(model_dict)
    engine_config = _build_engine_config(chosen_ec)

    # kv_offload scheme:name=介质(cpu/disk/cpu_disk);后端工具(mooncake/memcache)是 cpu 介质下的实现,scheme 名也为 cpu。
    # has_memory_method = 有内存卸载方法(name 含 cpu/cpu_disk,或 yaml 声明的后端 scheme);
    # has_disk = 有 disk 层(disk 或 cpu_disk)。模板存在性护栏:memory/disk 启用还需对应方法存在。
    kv_offload_block = smart_accel.get("kv_offload")
    names = (
        {s.get("name") for s in kv_offload_block if isinstance(s, dict)}
        if isinstance(kv_offload_block, list) else set()
    )
    has_disk = "disk" in names or "cpu_disk" in names
    # 内存方法:name=cpu/cpu_disk(native/lmcache),或 yaml 声明的后端 scheme(name=cpu;mooncake/memcache 按 connector 判定)。
    # 工具按 connector 内容路由(AscendStoreConnector),不再靠 KV_STORE_BACKEND env 选。
    has_backend = _has_backend_scheme(kv_offload_block)
    has_memory_method = ("cpu" in names or "cpu_disk" in names) or has_backend

    # MaaS 显式开关为唯一驱动(YAML 块存在不再自动启用);介质另需对应 scheme 模板存在
    enable_kv = flags.kv
    enable_sparse = flags.sparse

    # 后端 scheme 选中但未下 KV_MEM_OFFLOAD_SIZE → 视为 auto(按 pod 内存估算),避免容量静默=0
    mem_size_mode_raw = flags.memory_offload_size_mode
    if has_backend and not (mem_size_mode_raw or "").strip():
        mem_size_mode_raw = "auto"
    memory_intent, memory_size_mode, memory_capacity_gb = _resolve_memory_offload(mem_size_mode_raw)

    # memory_offload_size_mode 下发 auto/数值、且 YAML 有内存方法(cpu/cpu_disk 或选中 backend)时才开
    memory_on = memory_intent is True and enable_kv and has_memory_method
    disk_on = flags.disk and enable_kv and has_disk

    # 内存卸载容量来源:auto=从 pod 内存 + TP/DP 估算 / 数值字符串=固定 GB 值
    # tp_size = tensor_parallel_size(yaml 来源),无条件算:供 SmartKVCacheConfig.tp_size + auto 估算共用。
    tp = int((chosen_ec or {}).get("tensor_parallel_size", 1))
    explicit_memory_on = False
    if memory_on and memory_size_mode == "auto":
        dp = (chosen_ec or {}).get("data_parallel_size", 1)
        est = estimate_offload_memory(
            container_memory_gb=flags.pod_available_memory_gb,
            tp_size=tp,
            dp_size=dp,
            min_threshold_gb=flags.min_offload_threshold_gb,
        )
        if est.enabled:
            memory_capacity_gb = int(est.available_gb)
        elif explicit_memory_on:
            # 显式开启时尊重用户意图,即使估算不足也保留估算可用值(不低于 0)。
            memory_capacity_gb = max(int(est.available_gb), 0)
            logger.warning(
                "SmartAccel memory_offload_size_mode=auto estimate low but explicitly enabled: %s",
                est.disable_reason,
            )
        else:
            logger.warning("SmartAccel memory_offload_size_mode=auto: %s", est.disable_reason)
            memory_on = False

    smart_input = SmartAccelInput(
        hardware_config=hardware_config,
        model_config=model_config,
        engine_config=engine_config,
        deployment_mode=DeploymentMode(pd_role=flags.pd_role),
        smart_decoding_config=SmartDecodingConfig(
            enabled=flags.decoding_enabled,
            model_path=flags.decoding_model_path,
        ),
        smart_kv_cache_config=SmartKVCacheConfig(
            enabled=enable_kv,
            memory_offload_enabled=memory_on,
            memory_offload_size_mode=memory_size_mode,
            disk_offload_enabled=disk_on,
            disk_capacity_gb=flags.disk_gb,
            disk_path=flags.disk_path,
            qat_enabled=flags.qat,
            qat_device_count=flags.qat_devices,
            qat_compression_level=flags.qat_level,
            tp_size=tp,
        ),
        smart_kv_sparse_config=SmartKVSparseConfig(enabled=enable_sparse, mode=flags.sparse_level),
        smart_accel=smart_accel,
    )
    # 内部渲染容量:不作为 SmartKVCacheConfig 入参暴露,由 loader 根据 memory_offload_size_mode 解析。
    setattr(smart_input.smart_kv_cache_config, "_memory_capacity_gb", memory_capacity_gb)

    return smart_input


def _resolve_memory_offload(value: Optional[str]) -> tuple[Optional[bool], str, int]:
    """解析 KV_MEM_OFFLOAD_SIZE/ENABLE_KV_MEM_OFFLOAD:auto / 数值 GB / false / 未下发。"""
    if value is None:
        return None, "", 0
    raw = str(value).strip().lower()
    if raw in ("", "false", "0", "no", "off"):
        return False, "", 0
    if raw == "auto":
        return True, "auto", 0
    try:
        return True, raw, int(raw)
    except ValueError:
        logger.warning("Invalid memory_offload_size_mode=%r, disable memory offload", value)
        return False, "", 0


def _package_smart_accel_root() -> Path:
    """返回随 wings_accel 包分发的 smart-accel YAML 根目录。"""
    return Path(__file__).resolve().parent / "smart-accel"


def _resolve_smart_accel_root(config_root: Union[str, Path]) -> Path:
    """优先使用 config_root/smart-accel,否则回落到包内 smart-accel。"""
    root = Path(config_root) / "smart-accel"
    if root.exists():
        return root
    return _package_smart_accel_root()


def build_smart_accel_yaml_path(
    config_root: Union[str, Path],
    engine: str,
    engine_version: str,
    hardware_family: str,
    model_dir: str,
    yaml_name: str,
) -> Path:
    """拼 SmartAccel 配置路径。

    目录固定为 wings_accel/smart-accel/{engine}/v{version}/{hardware}/models/{model_dir}/{yaml_name}。
    config_root 参数保留用于兼容旧调用;若调用方显式传入带 smart-accel 的根目录,优先用于测试/外部覆盖。
    新调用优先使用 find_smart_accel_yaml_path 按 hardware models 目录扫描匹配。
    """
    root = _resolve_smart_accel_root(config_root)
    # build 路径无法像 find 那样多候选探测(调用方要确定单一路径),取归一化后的最后一个候选
    # (即最简渠道目录,如 v0.21.0rc);干净版本只有一个候选,行为不变。
    candidates = _candidate_version_dirs(str(engine_version))
    version_dir = candidates[-1] if candidates else f"v{str(engine_version).lstrip('v')}"
    return root / engine / version_dir / hardware_family / "models" / model_dir / yaml_name


def find_smart_accel_yaml_path(
    config_root: Union[str, Path],
    engine: str,
    engine_version: str,
    hardware_family: str,
    model_name: str,
) -> Optional[Path]:
    """按硬件目录扫描并匹配 SmartAccel YAML —— 三层优先级(对齐 docs/48 + 保留 stem 兜底)。

    MaaS 不下发精度参数,变体信号 = ``--model-name`` 带完整精度后缀(如 ``Qwen3.5-397B-A17B-nvfp4``)。
    匹配优先级(逐层回退,每层 1 命中→取 / >1 命中→报错 / 0 命中→落下一层):
    1. ``model.variant_name`` 与 model_name 小写归一**精确相等**(非正则)—— 确定性,无子串坑(docs/48 主路径)。
    2. ``model.match[].name_pattern`` 正则命中 model_name —— 家族级模糊兜底(docs/48 回退层)。
    3. ``model.name`` / ``model.model_id`` / 模型目录名 / yaml stem 与 model_name 精确匹配
       —— 单变体向后兼容兜底(存量无 model 块的 yaml 仍可定位)。

    全部 0 命中返回 None(上层 no-op)。

    Args:
        config_root: 配置根目录;优先 config_root/smart-accel,否则回落包内 smart-accel。
        engine: 引擎名(vllm / vllm-ascend / sglang)。
        engine_version: 引擎版本,可带可不带 v 前缀。
        hardware_family: 硬件目录名,如 rtx_pro_5000_48G。
        model_name: 待匹配模型名(= MaaS 下发的 --model-name,带完整精度后缀)。

    Returns:
        匹配的 yaml Path;无命中返回 None。

    Raises:
        ValueError: 某层命中 >1(variant_name 冲突 / name_pattern 或 stem 多变体歧义),
            错误信息带 model_name + 候选清单,避免静默选错。
    """
    root = _resolve_smart_accel_root(config_root)
    # 按"原始版本目录 → 归一化渠道目录"顺序查找,兼容构建版本号
    # (如 v0.21.0rc1-20260709144216 → v0.21.0rc)。与 version_resolver 候选顺序对齐:精确优先。
    candidate_dirs = _candidate_version_dirs(str(engine_version))
    models_dir: Optional[Path] = None
    for version_dir in candidate_dirs:
        candidate = root / engine / version_dir / hardware_family / "models"
        if candidate.is_dir():
            models_dir = candidate
            break
    if models_dir is None:
        logger.warning(
            "SmartAccel models dir not found under %s/%s/[candidates=%s]/%s",
            root, engine, candidate_dirs, hardware_family,
        )
        return None

    # 三层分桶:同一文件只入其命中的最高优先层(if/elif),逐层判定,与 docs/48 逐层回退等价。
    exact_variant: list[Path] = []   # ① variant_name 精确
    pattern_hits: list[Path] = []    # ② name_pattern 正则
    stem_hits: list[Path] = []       # ③ 目录名/stem 精确兜底
    yaml_errors: list[tuple[Path, str]] = []
    for yaml_file in sorted(models_dir.glob("*/*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            yaml_errors.append((yaml_file, str(exc)))
            logger.warning("SmartAccel YAML parse failed %s: %s", yaml_file, exc)
            continue
        if not isinstance(data, dict):
            continue
        if _match_variant_name(data, model_name):
            exact_variant.append(yaml_file)
        elif _match_name_pattern(data, yaml_file, model_name):
            pattern_hits.append(yaml_file)
        elif _match_stem(data, yaml_file, model_name):
            stem_hits.append(yaml_file)

    # ① variant_name 精确优先(确定性,docs/48 主路径)
    if len(exact_variant) == 1:
        logger.info("SmartAccel: model '%s' 精确命中 variant_name in %s", model_name, exact_variant[0])
        return exact_variant[0]
    if len(exact_variant) > 1:
        raise ValueError(
            f"variant_name 冲突:多个 SmartAccel YAML 声明 variant_name='{model_name}': "
            + ", ".join(str(p) for p in exact_variant)
            + "。请确保同目录 variant_name 两两不重复。"
        )

    # ② name_pattern 模糊回退
    if len(pattern_hits) == 1:
        logger.info("SmartAccel: model '%s' name_pattern matched in %s", model_name, pattern_hits[0])
        return pattern_hits[0]
    if len(pattern_hits) > 1:
        raise ValueError(
            f"Ambiguous SmartAccel YAML: model_name='{model_name}' 经 name_pattern 命中多个文件: "
            + ", ".join(str(p) for p in pattern_hits)
            + "。多变体请传带精度后缀的完整 --model-name(= 各文件 model.variant_name)。"
        )

    # ③ 目录名/stem 精确兜底(单变体向后兼容)
    if len(stem_hits) == 1:
        logger.info("SmartAccel: model '%s' stem/dir matched in %s", model_name, stem_hits[0])
        return stem_hits[0]
    if len(stem_hits) > 1:
        raise ValueError(
            f"Ambiguous SmartAccel YAML: model_name='{model_name}' 命中多个文件(目录名/stem): "
            + ", ".join(str(p) for p in stem_hits)
        )

    msg = f"No SmartAccel YAML matched model_name='{model_name}' under {models_dir}"
    if yaml_errors:
        details = "; ".join(f"{p}: {e}" for p, e in yaml_errors)
        msg += f"; YAML parse errors encountered: {details}"
    logger.warning(msg)
    return None


def load_smart_accel_from_config(
    config_root: Union[str, Path],
    engine: str,
    engine_version: str,
    hardware_family: str,
    model_name: str,
    flags: Optional[LoadFlags] = None,
) -> Optional[SmartAccelInput]:
    """按 smart-accel 硬件目录扫描定位并读取模型 YAML;缺失返回 None。"""
    yaml_path = find_smart_accel_yaml_path(
        config_root,
        engine,
        engine_version,
        hardware_family,
        model_name,
    )
    if yaml_path is None:
        return None
    smart_input = load_smart_accel_from_yaml(str(yaml_path), flags)
    if smart_input is not None:
        # smart-accel 根目录供 files 条目 src 解析(kv_backends/<backend>/ 模板)。
        smart_input.config_root = str(_resolve_smart_accel_root(config_root))
    return smart_input


def _match_variant_name(data: Dict[str, Any], model_name: str) -> bool:
    """① 精确层:model.variant_name 与 model_name 小写归一后精确相等(非正则)。

    variant_name = MaaS 对本文件下发的【完整 --model-name】(带精度后缀);显式声明、不推断。
    docs/48 主路径:精确相等无正则子串坑,多变体发全名即唯一命中。

    Args:
        data: 已解析的 yaml dict。
        model_name: 待匹配模型名。

    Returns:
        variant_name 存在且与 model_name 精确相等(忽略大小写/首尾空白)→ True;否则 False。
    """
    model_block = data.get("model", {})
    if not isinstance(model_block, dict):
        return False
    variant_name = model_block.get("variant_name")
    if not isinstance(variant_name, str) or not variant_name.strip():
        return False
    return variant_name.strip().lower() == model_name.strip().lower()


def _match_name_pattern(data: Dict[str, Any], yaml_file: Path, model_name: str) -> bool:
    """② 模糊层:model.match[].name_pattern 正则 re.search 命中 model_name(家族级兜底)。

    docs/48 回退层:精确层零命中时,用家族级 name_pattern 容错(家族名/大小写漂移/向后兼容)。
    非法正则不中断全量扫描:记日志后跳过该规则。

    Args:
        data: 已解析的 yaml dict。
        yaml_file: yaml 路径(仅用于非法正则的日志定位)。
        model_name: 待匹配模型名。

    Returns:
        任一 name_pattern 命中 → True;否则 False。
    """
    model_block = data.get("model", {})
    if not isinstance(model_block, dict):
        return False
    match_rules = model_block.get("match", [])
    if not isinstance(match_rules, list):
        return False
    for rule in match_rules:
        if not isinstance(rule, dict):
            continue
        pattern = rule.get("name_pattern", "")
        if not pattern:
            continue
        try:
            if re.search(pattern, model_name):
                return True
        except re.error as exc:
            logger.warning(
                "SmartAccel: invalid name_pattern %r in %s: %s (skip this rule)",
                pattern, yaml_file, exc,
            )
            continue
    return False


def _match_stem(data: Dict[str, Any], yaml_file: Path, model_name: str) -> bool:
    """③ 向后兼容兜底:model.name / model.model_id / 目录名 / yaml stem 与 model_name 精确相等。

    供无 model 块的存量单变体 yaml 定位。docs/48 不推荐用 model_id/文件名做消歧键
    (真实数据证明不可靠),但 wings_accel 存量 yaml 依赖此兜底,作最低优先层保留。

    Args:
        data: 已解析的 yaml dict。
        yaml_file: yaml 路径(取 parent.name / stem 作候选)。
        model_name: 待匹配模型名。

    Returns:
        任一候选与 model_name(或其 basename)小写归一后相等 → True;否则 False。
    """
    model_block = data.get("model", {}) if isinstance(data.get("model"), dict) else {}
    candidates = [model_block.get("name"), model_block.get("model_id")]
    candidates.extend([yaml_file.parent.name, yaml_file.stem])
    names = {_normalize_model_name(v) for v in candidates if v}
    requested = {
        _normalize_model_name(model_name),
        _normalize_model_name(Path(model_name).name),
    }
    return bool(names & requested)


def _normalize_model_name(value: str) -> str:
    """模型名匹配用的轻量归一化。"""
    return str(value).strip().lower()


def _get_chosen_engine_config(model_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 scenarios.{topology}.strategies.{name}.engine_config 取选中的 engine_config dict。

    取第一个 default_strategy=true 的策略;若都没有,取第一个策略。
    缺失时返回 None。
    """
    scenarios = model_dict.get("scenarios", {}) or {}
    for _, topo_block in scenarios.items():
        strategies = (topo_block or {}).get("strategies", {}) or {}
        default_block = None
        first_block = None
        for _, strat in strategies.items():
            if first_block is None:
                first_block = strat
            if (strat or {}).get("default_strategy"):
                default_block = strat
                break
        chosen = default_block or first_block
        if chosen and chosen.get("engine_config"):
            return chosen["engine_config"]
    return None


def _build_engine_config(ec: Optional[Dict[str, Any]]) -> EngineConfig:
    """从 engine_config dict 构建 EngineConfig。

    缺失时返回 EngineConfig() 默认值(vllm / 0.22.0)。
    """
    if not ec:
        return EngineConfig()
    return EngineConfig(
        name=ec.get("engine", "vllm"),
        version=ec.get("version", "0.22.0"),
    )
