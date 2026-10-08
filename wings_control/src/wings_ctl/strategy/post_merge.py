"""配置合并后的最终约束策略。

本模块只处理依赖最终合并结果的约束，不参与模板选择或参数 merge。
当前规则：vLLM Ascend 的 FlashComm1 / DSA-CP 仅支持 TP >= 2。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from wings_ctl.core.models import SourceEvent, TracedValue
from wings_ctl.utils.env_utils import get_interface_for_ip, get_local_ip

_FLASHCOMM1_ENV = "VLLM_ASCEND_ENABLE_FLASHCOMM1"
_NETWORK_IP_ENV = "HCCL_IF_IP"
_NETWORK_INTERFACE_ENVS = (
    "NETWORK_CARD_NAME",
    "GLOO_SOCKET_IFNAME",
    "NCCL_SOCKET_IFNAME",
    "TP_SOCKET_IFNAME",
    "HCCL_SOCKET_IFNAME",
)
_DSA_CP_KEY = "enable_dsa_cp"
_TP_KEY = "tensor_parallel_size"


@dataclass(frozen=True)
class PostMergeStrategyResult:
    """最终约束策略产出的配置和审计说明。"""

    engine_config_traces: Dict[str, TracedValue]
    env_traces: Dict[str, TracedValue]
    notes: Dict[str, str]


def _tp_supports_dependent_params(engine_config_traces: Dict[str, TracedValue]) -> bool:
    """判断最终 TP 是否支持依赖参数；缺省 TP 按 1 处理。"""
    traced = engine_config_traces.get(_TP_KEY)
    if traced is None or traced.final_value is None:
        return False
    try:
        return int(traced.final_value) >= 2
    except (TypeError, ValueError):
        # multi-node 占位值（如 $7）留给运行时注入处理。
        return True


def _remove_dsa_cp_from_additional_config(value: Any) -> tuple[Any, bool]:
    """仅从 additional_config 的配置树中移除 enable_dsa_cp。"""
    if not isinstance(value, dict):
        return value, False
    if _DSA_CP_KEY not in value:
        return value, False
    cleaned = dict(value)
    del cleaned[_DSA_CP_KEY]
    return cleaned, True


def apply_network_env_strategy(
    env_traces: Dict[str, TracedValue],
) -> tuple[Dict[str, TracedValue], Dict[str, str]]:
    """以本 Pod IP 及所属网卡覆盖已声明的通信环境变量。

    仅覆盖 YAML 已声明的通信 IP 和网卡变量（含 NCCL），不为其他引擎或 recipe 注入新变量。每个改写
    都追加独立 trace event，使 audit 可同时看到原 YAML 值、最终值和覆盖原因。
    """
    target_keys = [key for key in (_NETWORK_IP_ENV, *_NETWORK_INTERFACE_ENVS) if key in env_traces]
    if not target_keys:
        return env_traces, {}
    if all(env_traces[key].final_layer == "strategy_network_env" for key in target_keys):
        return env_traces, {}

    local_ip = get_local_ip()
    interface, matched = get_interface_for_ip(local_ip)
    discovery = "matched" if matched else "fallback_eth0"
    result = dict(env_traces)
    for key in target_keys:
        value = local_ip if key == _NETWORK_IP_ENV else interface
        reason = "get_local_ip" if key == _NETWORK_IP_ENV else f"interface_for_local_ip:{discovery}"
        previous = env_traces[key]
        event = SourceEvent(
            action="override",
            layer="strategy_network_env",
            value=value,
            source_file="<strategy:network_env>",
            source_path=reason,
        )
        result[key] = TracedValue(
            final_value=value,
            final_layer="strategy_network_env",
            source_file="<strategy:network_env>",
            source_path=reason,
            events=previous.events + [event],
        )
    notes = {
        "network_env_override.status": "applied",
        "network_env_override.local_ip": local_ip,
        "network_env_override.interface": interface,
        "network_env_override.interface_discovery": discovery,
        "network_env_override.keys": ",".join(target_keys),
    }
    return result, notes


def apply_post_merge_strategy(
    engine_config_traces: Dict[str, TracedValue],
    env_traces: Dict[str, TracedValue],
    *,
    engine: str,
) -> PostMergeStrategyResult:
    """根据最终 TP 过滤不兼容参数。

    该策略必须在 model / strategy / feature / accel / user_cli 全部 merge 完成后调用，
    这样用户最终覆盖的 tensor_parallel_size 也会参与判断。

    非 vLLM Ascend 或 TP >= 2 时不修改配置；TP 缺失、None 或小于 2 时移除
    ``additional_config.enable_dsa_cp`` 和 ``VLLM_ASCEND_ENABLE_FLASHCOMM1``。
    """
    if engine != "vllm-ascend" or _tp_supports_dependent_params(engine_config_traces):
        return PostMergeStrategyResult(engine_config_traces, env_traces, {})

    filtered_engine: Dict[str, TracedValue] = {}
    removed_dsa = False
    for key, traced in engine_config_traces.items():
        # 处理 enable_dsa_cp。
        if key == _DSA_CP_KEY:
            removed_dsa = True
            continue
        if key == "additional_config":
            cleaned_value, changed = _remove_dsa_cp_from_additional_config(traced.final_value)
            if changed:
                removed_dsa = True
                if not cleaned_value:
                    continue
                events = list(traced.events)
                events.append(
                    SourceEvent(
                        action="remove",
                        layer="strategy_post_merge",
                        value=None,
                        source_file="<strategy:post_merge>",
                        source_path="additional_config.enable_dsa_cp",
                    )
                )
                traced = TracedValue(
                    final_value=cleaned_value,
                    final_layer="strategy_post_merge",
                    source_file="<strategy:post_merge>",
                    source_path="additional_config",
                    events=events,
                )
        filtered_engine[key] = traced

    # 处理 VLLM_ASCEND_ENABLE_FLASHCOMM1。
    removed_flashcomm = _FLASHCOMM1_ENV in env_traces
    filtered_env = {
        key: traced
        for key, traced in env_traces.items()
        if key != _FLASHCOMM1_ENV
    }

    removed = []
    if removed_dsa:
        removed.append(_DSA_CP_KEY)
    if removed_flashcomm:
        removed.append(_FLASHCOMM1_ENV)
    notes = {
        "post_merge_tp_dependent.status": "removed" if removed else "noop",
        "post_merge_tp_dependent.reason": "tensor_parallel_size<2",
        "post_merge_tp_dependent.removed": ",".join(removed) if removed else "none",
    }
    return PostMergeStrategyResult(filtered_engine, filtered_env, notes)
