"""MindIE 单机与双机共享的参数解析和能力边界。

本模块把 trace-first 平面配置转换为强类型共享设置，只处理版本、硬件、模型、
长度和调度等真正与 topology 无关的事实。设备 rank、ranktable、HCCL 和并行布局
分别由 standalone/dual_node 负责，避免共享对象被大量双机可选字段污染。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from wings_ctl.core.models import ResolvedConfig


# 这是“配置 schema 已验证版本”而非最低版本。版本回退也必须失败，防止使用
# 2.3.0 的嵌套投影修改结构可能已经变化的新版本 config.json。
SUPPORTED_MINDIE_VERSION = "2.3.0"
DEFAULT_MINDIE_WORK_DIR = "/usr/local/Ascend/mindie/latest/mindie-service"
CONFIG_TEMPLATE_NAME = "mindie_service_config.json"

# 未知键采用 fail-fast，不做静默过滤。MindIE 最终 argv 无法反映 config.json 丢参，
# 若在这里放行，audit 会显示参数已应用而 runtime 实际未消费。
SUPPORTED_KEYS = frozenset(
    {
        "host",
        "ipAddress",
        "port",
        "model",
        "model_path",
        "modelWeightPath",
        "served_model_name",
        "model_name",
        "modelName",
        "max_seq_len",
        "maxSeqLen",
        "max_input_token_len",
        "maxInputTokenLen",
        "max_iter_times",
        "maxIterTimes",
        "max_prefill_tokens",
        "maxPrefillTokens",
        "trust_remote_code",
        "trustRemoteCode",
        "npu_memory_fraction",
        "local_device_count",
        # 这些键只描述项目侧模型策略，不是用户 CLI，也不会原样写入厂商配置。
        "mindie_is_moe",
        "mindie_ep_enabled",
        "mindie_ep_policy",
        "mindie_moe_tp",
        "mindie_ep_level",
        "mindie_model_family",
    }
)


@dataclass(frozen=True)
class MindieModelPolicy:
    """由模型 YAML 决定的 MindIE 能力策略。

    用户不需要也不允许理解 EP 组合。领域层只在模型 profile 明确声明支持时开启
    EP；未匹配 profile 的模型保持基础启动路径，不能根据模型名或参数规模猜测。
    """

    is_moe: bool = False
    ep_enabled: bool = False
    ep_policy: str | None = None
    moe_tp: int | None = None
    ep_level: int | None = None
    model_family: str | None = None


@dataclass(frozen=True)
class MindieParallelPlan:
    """已计算的 MindIE 并行结果；公共并行模块不读取这些字段。"""

    parallel_world_size: int
    tp: int | None = None
    dp: int | None = None
    moe_tp: int | None = None
    moe_ep: int | None = None
    ep_level: int | None = None
    model_family: str | None = None

    @property
    def ep_enabled(self) -> bool:
        return self.moe_ep is not None


@dataclass(frozen=True)
class MindieCommonSettings:
    """已校验的共享设置；字段均可直接交给 2.3.0 config projector。"""

    host: str
    port: int
    model_path: str
    model_name: str
    max_seq_len: int
    max_input_token_len: int
    max_iter_times: int
    max_prefill_tokens: int
    trust_remote_code: bool
    npu_memory_fraction: float
    configured_local_device_count: int
    model_policy: MindieModelPolicy
    config_template_path: Path
    # Resolver 已经完成 env 多层合并；runtime 仅需在厂商 set_env 后重新导出最终值。
    static_env: tuple[tuple[str, Any], ...]


def final_values(resolved: ResolvedConfig) -> Dict[str, Any]:
    """读取 trace 终值，不在领域层再次合并或修改来源链。"""
    return {
        key: traced.final_value
        for key, traced in resolved.engine_config_traces.items()
        if traced.final_value is not None
    }


def first(values: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """按 canonical 到兼容别名顺序取值，并保留合法的 ``False``/``0``。"""
    for key in keys:
        if key in values:
            return values[key]
    return default


def positive_int(name: str, value: Any) -> int:
    """规范正整数并显式拒绝属于 ``int`` 子类的布尔值。"""
    if isinstance(value, bool):
        raise ValueError(f"MindIE parameter '{name}' must be a positive integer, got {value!r}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"MindIE parameter '{name}' must be a positive integer, got {value!r}") from exc
    if parsed <= 0:
        raise ValueError(f"MindIE parameter '{name}' must be > 0, got {parsed}")
    return parsed


def _normalize_version(value: str | None) -> str:
    return (value or "").strip().lstrip("vV")


def _strict_bool(name: str, value: Any) -> bool:
    """模型策略字段禁止使用 0/1 或字符串，避免 YAML 写错后静默改变并行布局。"""
    if not isinstance(value, bool):
        raise ValueError(f"MindIE model policy '{name}' must be boolean, got {value!r}")
    return value


def _resolve_model_policy(values: Dict[str, Any]) -> MindieModelPolicy:
    """从最终 trace 解析模型能力，不读取用户未提供的权重元数据做策略猜测。"""
    is_moe = _strict_bool("mindie_is_moe", values.get("mindie_is_moe", False))
    ep_enabled = _strict_bool("mindie_ep_enabled", values.get("mindie_ep_enabled", False))
    family_raw = values.get("mindie_model_family")
    family = str(family_raw).strip() if family_raw is not None else None

    if ep_enabled and not is_moe:
        raise ValueError("MindIE EP cannot be enabled for a dense model profile")
    if not ep_enabled:
        return MindieModelPolicy(is_moe=is_moe, model_family=family or None)

    policy = str(values.get("mindie_ep_policy", "")).strip()
    if policy != "full_world":
        raise ValueError("MindIE EP-enabled profile requires mindie_ep_policy='full_world'")
    if not family:
        raise ValueError("MindIE EP-enabled profile requires mindie_model_family for config projection")
    moe_tp = positive_int("mindie_moe_tp", values.get("mindie_moe_tp", 1))
    ep_level = positive_int("mindie_ep_level", values.get("mindie_ep_level"))
    if ep_level not in (1, 2):
        raise ValueError(f"MindIE mindie_ep_level must be 1 or 2, got {ep_level}")
    return MindieModelPolicy(
        is_moe=True,
        ep_enabled=True,
        ep_policy=policy,
        moe_tp=moe_tp,
        ep_level=ep_level,
        model_family=family,
    )


def _resolve_config_template_path(resolved: ResolvedConfig) -> Path:
    """定位与已解析版本相同的项目模板，不回退到 MindIE 安装目录。

    正常 Pipeline 由 ``resolved_version_dir`` 提供真实 config root；仓库内直接构造
    ``ResolvedConfig`` 的兼容测试没有该 note，才使用当前源码仓库的固定资产路径。
    无论走哪条路径，模板缺失都由 projector fail-fast。
    """
    version_dir = resolved.resolution_notes.get("resolved_version_dir")
    if version_dir:
        return Path(version_dir) / CONFIG_TEMPLATE_NAME
    return (
        Path(__file__).resolve().parents[4]
        / "config"
        / "engines"
        / "mindie"
        / f"v{SUPPORTED_MINDIE_VERSION}"
        / CONFIG_TEMPLATE_NAME
    )


def build_parallel_plan(
    policy: MindieModelPolicy,
    parallel_world_size: int,
    *,
    require_tp_dp: bool,
) -> MindieParallelPlan:
    """结合 topology 规模计算模型 YAML 声明的并行策略。

    ``require_tp_dp`` 仅用于 MindIE 双机：2.3.0 多节点必须显式写普通 ``tp/dp``。
    EP 的启用只由模型 profile 决定；稠密或 TP-only profile 不会得到 MoE 字段。
    """
    world_size = positive_int("parallel_world_size", parallel_world_size)
    tp = world_size if require_tp_dp or policy.ep_enabled else None
    dp = 1 if require_tp_dp or policy.ep_enabled else None
    if not policy.ep_enabled:
        return MindieParallelPlan(
            parallel_world_size=world_size,
            tp=tp,
            dp=dp,
            model_family=policy.model_family,
        )

    # 首期只有 full_world：专家组覆盖全部 rank，moe_tp 由模型 YAML 固定。
    # 不能整除意味着模型 recipe 与实际部署规模不兼容，必须在脚本落盘前失败。
    if policy.moe_tp is None:
        raise ValueError("MindIE EP-enabled profile is missing mindie_moe_tp")
    if world_size % policy.moe_tp != 0:
        raise ValueError(
            "MindIE EP parallelism requires parallel_world_size divisible by "
            f"mindie_moe_tp; got {world_size} % {policy.moe_tp}"
        )
    moe_ep = world_size // policy.moe_tp
    if moe_ep * policy.moe_tp != world_size:
        raise ValueError("MindIE EP parallelism product does not match world size")
    return MindieParallelPlan(
        parallel_world_size=world_size,
        tp=tp,
        dp=dp,
        moe_tp=policy.moe_tp,
        moe_ep=moe_ep,
        ep_level=policy.ep_level,
        model_family=policy.model_family,
    )


def resolve_common_settings(resolved: ResolvedConfig) -> MindieCommonSettings:
    """校验共享能力边界并返回强类型参数。

    该函数不判断单机或双机，也不读 ranktable。错误引擎、非 Ascend、版本回退、
    accel 结果、未知参数及字段关系均在生成脚本前 fail-fast。
    """
    if resolved.engine != "mindie":
        raise ValueError(f"MindIE extension received engine={resolved.engine!r}")
    if resolved.hardware.device.strip().lower() != "ascend":
        raise ValueError(f"MindIE requires Ascend hardware, got device={resolved.hardware.device!r}")

    version = _normalize_version(resolved.engine_version.resolved or resolved.engine_version.requested)
    if resolved.engine_version.is_fallback or version != SUPPORTED_MINDIE_VERSION:
        raise ValueError(
            "MindIE extension requires an exact 2.3.0 config match; "
            f"requested={resolved.engine_version.requested!r}, "
            f"resolved={resolved.engine_version.resolved!r}, "
            f"fallback={resolved.engine_version.is_fallback}"
        )
    if resolved.accel.enabled:
        # wings-accel 仍产出 argv 型参数，尚未定义到 MindIE config.json 的可靠投影。
        # 禁止静默忽略，确保 audit 的 enable 状态与最终运行效果一致。
        raise NotImplementedError("wings-accel output is not supported by the MindIE extension")

    values = final_values(resolved)
    unknown = sorted(set(values) - SUPPORTED_KEYS)
    if unknown:
        raise ValueError("MindIE extension received unsupported engine_config key(s): " + ", ".join(unknown))

    host = str(first(values, "host", "ipAddress", default="0.0.0.0")).strip()
    if not host:
        raise ValueError("MindIE host/ipAddress must not be empty")
    port = positive_int("port", first(values, "port", default=17000))
    if port > 65535:
        raise ValueError(f"MindIE port must be <= 65535, got {port}")

    model_path = str(first(values, "model", "model_path", "modelWeightPath", default="")).strip()
    if not model_path:
        raise ValueError("MindIE requires --model-path (model/modelWeightPath is empty)")
    model_name = str(
        first(
            values,
            "served_model_name",
            "model_name",
            "modelName",
            default=Path(model_path).name,
        )
    ).strip()
    if not model_name:
        raise ValueError("MindIE modelName must not be empty")

    max_input = positive_int(
        "max_input_token_len",
        first(values, "max_input_token_len", "maxInputTokenLen", default=2048),
    )
    max_iter = positive_int(
        "max_iter_times",
        first(values, "max_iter_times", "maxIterTimes", default=2048),
    )
    max_seq = positive_int(
        "max_seq_len",
        first(values, "max_seq_len", "maxSeqLen", default=max_input + max_iter),
    )
    if max_seq < max_input + max_iter:
        raise ValueError(
            "MindIE max_seq_len must be >= max_input_token_len + max_iter_times; "
            f"got {max_seq} < {max_input} + {max_iter}"
        )
    max_prefill = positive_int(
        "max_prefill_tokens",
        first(
            values,
            "max_prefill_tokens",
            "maxPrefillTokens",
            default=max(8192, max_input),
        ),
    )
    if max_prefill < max_input:
        raise ValueError(f"MindIE max_prefill_tokens must be >= max_input_token_len; got {max_prefill} < {max_input}")

    trust = first(values, "trust_remote_code", "trustRemoteCode", default=False)
    if not isinstance(trust, bool):
        raise ValueError(f"MindIE trust_remote_code must be boolean, got {trust!r}")
    try:
        npu_fraction = float(first(values, "npu_memory_fraction", default=0.96))
    except (TypeError, ValueError) as exc:
        raise ValueError("MindIE npu_memory_fraction must be numeric") from exc
    if not 0 < npu_fraction <= 1:
        raise ValueError(f"MindIE npu_memory_fraction must be in (0, 1], got {npu_fraction}")

    return MindieCommonSettings(
        host=host,
        port=port,
        model_path=model_path,
        model_name=model_name,
        max_seq_len=max_seq,
        max_input_token_len=max_input,
        max_iter_times=max_iter,
        max_prefill_tokens=max_prefill,
        trust_remote_code=trust,
        npu_memory_fraction=npu_fraction,
        configured_local_device_count=positive_int(
            "local_device_count",
            first(values, "local_device_count", default=1),
        ),
        model_policy=_resolve_model_policy(values),
        config_template_path=_resolve_config_template_path(resolved),
        static_env=tuple(
            (key, traced.final_value) for key, traced in resolved.env_traces.items() if traced.final_value is not None
        ),
    )
