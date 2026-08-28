"""特性注入层:根据 feature_switches 和 engine 类型,注入引擎参数和环境变量。

职责:
- 不依赖模板内容,只依赖开关和引擎类型
- 只返回覆盖层(override)和说明信息(notes),不原地修改
- 由外层统一合并并写入 trace

当前支持的特性:
- SmartQoS: 优先级调度参数
- EnableTrace: OTLP 链路追踪参数 + OTEL 环境变量
- Metrics: 监控指标参数
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _inject_smartqos(switches: dict, engine: str) -> tuple[dict, dict, dict]:
    """SmartQoS 特性注入：引擎参数。

    vLLM: --scheduling-policy priority
    SGLang: --enable-priority-scheduling --schedule-low-priority-values-first
            --priority-scheduling-preemption-threshold 20
    """
    if not switches.get("enable_smartqos"):
        return {}, {}, {}
    override: dict[str, Any] = {}
    env: dict[str, str] = {}
    notes: dict[str, str] = {"feature_inject.smartqos": "enabled"}

    if engine in ("vllm", "vllm-ascend"):
        override["scheduling_policy"] = "priority"
        notes["feature_inject.smartqos.vllm"] = "scheduling_policy=priority"
    elif engine in ("sglang",):
        override["enable_priority_scheduling"] = True
        override["schedule_low_priority_values_first"] = True
        override["priority_scheduling_preemption_threshold"] = 20
        notes["feature_inject.smartqos.sglang"] = (
            "enable_priority_scheduling, schedule_low_priority_values_first, "
            "priority_scheduling_preemption_threshold=20"
        )
    else:
        notes["feature_inject.smartqos.skip"] = f"engine={engine} not supported"

    return override, env, notes


def _inject_otlp_traces(switches: dict, engine: str) -> tuple[dict, dict, dict]:
    """EnableTrace 特性注入：引擎参数 + OTEL 环境变量。

    从 wings-control 侧环境变量 ``OTLP_TRACES_ENDPOINT`` 读取 OTLP 端点地址
    （由外部部署环境设置，如 K8s Deployment env），默认 ``localhost:4317``。
    该端点值注入到引擎参数 ``--otlp-traces-endpoint``，同时 OTEL 环境变量
    写入 ``start_command.sh`` 供引擎进程消费。

    注意：``OTLP_TRACES_ENDPOINT`` 本身不需要写入 ``start_command.sh``，
    引擎通过 ``--otlp-traces-endpoint`` CLI 参数获取端点地址。
    """
    if not switches.get("enable_otlp_traces"):
        return {}, {}, {}

    endpoint = os.environ.get("OTLP_TRACES_ENDPOINT", "localhost:4317")
    hostname = os.environ.get("HOSTNAME", "localhost")
    override: dict[str, Any] = {}
    env: dict[str, str] = {
        "OTEL_EXPORTER_OTLP_TRACES_INSECURE": "true",
        "OTEL_RESOURCE_ATTRIBUTES": f"service.instance.id={hostname},k8s.pod.name={hostname}",
    }
    notes: dict[str, str] = {"feature_inject.otlp_traces": f"endpoint={endpoint}"}

    if engine in ("vllm", "vllm-ascend"):
        override["otlp_traces_endpoint"] = endpoint
        env["OTEL_SERVICE_NAME"] = "vllm-server"
        notes["feature_inject.otlp_traces.vllm"] = "otlp_traces_endpoint"
    elif engine in ("sglang",):
        override["enable_trace"] = True
        override["otlp_traces_endpoint"] = endpoint
        env["OTEL_SERVICE_NAME"] = "sglang"
        env["SGLANG_TRACE_LEVEL"] = "2"
        notes["feature_inject.otlp_traces.sglang"] = "enable_trace, otlp_traces_endpoint"
    else:
        notes["feature_inject.otlp_traces.skip"] = f"engine={engine} not supported"

    return override, env, notes


def _inject_rag_acc(switches: dict, _engine: str) -> tuple[dict, dict, dict]:
    """Propagate the proxy-owned RAG switch into generated runtime scripts."""
    if "enable_rag_acc" not in switches:
        return {}, {}, {}
    enabled = bool(switches["enable_rag_acc"])
    value = "true" if enabled else "false"
    state = "enabled" if enabled else "disabled"
    return {}, {"RAG_ACC_ENABLED": value}, {"feature_inject.rag_acc": state}


def _inject_metrics(switches: dict, engine: str) -> tuple[dict, dict, dict]:
    """Metrics 特性注入：仅 SGLang 需要引擎参数，vLLM 默认开启。"""
    if not switches.get("enable_metrics"):
        return {}, {}, {}
    override: dict[str, Any] = {}
    env: dict[str, Any] = {}
    notes: dict[str, str] = {"feature_inject.metrics": "enabled"}

    if engine in ("sglang",):
        override["enable_metrics"] = True
        notes["feature_inject.metrics.sglang"] = "enable_metrics"
    elif engine in ("vllm", "vllm-ascend"):
        notes["feature_inject.metrics.vllm"] = "default_on, no_inject"
    else:
        notes["feature_inject.metrics.skip"] = f"engine={engine} not supported"

    return override, env, notes


# 特性注入器注册表：开关名 → 注入函数
# 后续新增特性时，只需在此注册表中添加条目，无需修改 feature_inject_transform 主体
_FEATURE_INJECTORS: dict[str, Callable[[dict, str], tuple[dict, dict, dict]]] = {
    "enable_smartqos": _inject_smartqos,
    "enable_otlp_traces": _inject_otlp_traces,
    "enable_rag_acc": _inject_rag_acc,
    "enable_metrics": _inject_metrics,
}


def feature_inject_transform(
    switches: dict,
    engine: str,
) -> tuple[dict, dict, dict]:
    """特性注入入口：遍历注册表，汇总 override、env_layer 与 notes。

    Args:
        switches: 特性开关 dict（如 ``{"enable_smartqos": True, ...}``）。
        engine: 引擎名称（如 ``"vllm"``、``"sglang"``）。

    Returns:
        ``(overrides, env_layer, notes)``:各特性注入结果的合并。
        三者都为空表示无特性开启。
    """
    override: dict[str, Any] = {}
    env: dict[str, str] = {}
    notes: dict[str, str] = {}

    for _, injector in _FEATURE_INJECTORS.items():
        o, e, n = injector(switches, engine)
        override.update(o)
        env.update(e)
        notes.update(n)

    return override, env, notes
