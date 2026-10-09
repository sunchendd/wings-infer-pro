"""FeatureInject 特性注入层单测。

对应实现 src/wings_ctl/strategy/feature_inject.py。覆盖:
- SmartQoS: vLLM/SGLang 引擎参数注入、不支持的引擎 skip
- EnableTrace: vLLM/SGLang 引擎参数 + OTEL 环境变量注入、不支持的引擎 skip
- Metrics: SGLang 引擎参数注入、vLLM default_on no_inject、不支持的引擎 skip
- feature_inject_transform: 多开关合并、无开关 no-op、notes 汇总
"""

from __future__ import annotations

from wings_ctl.strategy.feature_inject import (
    _inject_metrics,
    _inject_otlp_traces,
    _inject_rag_acc,
    _inject_smartqos,
    feature_inject_transform,
)


# ── _inject_smartqos ──────────────────────────────────────────────────────


def test_smartqos_vllm() -> None:
    """验证 vLLM 开 SmartQoS → 注入 scheduling_policy=priority。"""
    override, env, notes = _inject_smartqos({"enable_smartqos": True}, "vllm")
    assert override == {"scheduling_policy": "priority"}
    assert not env
    assert notes["feature_inject.smartqos"] == "enabled"
    assert notes["feature_inject.smartqos.vllm"] == "scheduling_policy=priority"


def test_smartqos_vllm_ascend() -> None:
    """验证 vllm-ascend 与 vllm 共用同一注入逻辑。"""
    override, _, notes = _inject_smartqos({"enable_smartqos": True}, "vllm-ascend")
    assert override == {"scheduling_policy": "priority"}
    assert notes["feature_inject.smartqos.vllm"] == "scheduling_policy=priority"


def test_smartqos_sglang() -> None:
    """验证 SGLang 开 SmartQoS → 注入三个 priority 调度参数。"""
    override, _, notes = _inject_smartqos({"enable_smartqos": True}, "sglang")
    assert override == {
        "enable_priority_scheduling": True,
        "schedule_low_priority_values_first": True,
        "priority_scheduling_preemption_threshold": 20,
    }
    assert notes["feature_inject.smartqos.sglang"] == (
        "enable_priority_scheduling, schedule_low_priority_values_first, "
        "priority_scheduling_preemption_threshold=20"
    )


def test_smartqos_unsupported_engine_skip() -> None:
    """验证不支持的引擎(如 mindie)→ skip,仅记录 notes,不注入参数。"""
    override, env, notes = _inject_smartqos({"enable_smartqos": True}, "mindie")
    assert not override
    assert not env
    assert "feature_inject.smartqos.skip" in notes
    assert "mindie" in notes["feature_inject.smartqos.skip"]


def test_smartqos_switch_off_is_noop() -> None:
    """验证开关未开 → no-op(空 override/env/notes)。"""
    override, env, notes = _inject_smartqos({}, "vllm")
    assert not override
    assert not env
    assert not notes


# ── _inject_otlp_traces ───────────────────────────────────────────────────


def test_otlp_vllm(monkeypatch) -> None:
    """验证 vLLM 开 EnableTrace → 注入 otlp_traces_endpoint + OTEL_SERVICE_NAME。"""
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", "collector:4317")
    monkeypatch.setenv("HOSTNAME", "pod-abc")
    override, env, notes = _inject_otlp_traces({"enable_otlp_traces": True}, "vllm")
    assert override == {"otlp_traces_endpoint": "collector:4317"}
    assert env["OTEL_SERVICE_NAME"] == "vllm-server"
    assert env["OTEL_EXPORTER_OTLP_TRACES_INSECURE"] == "true"
    assert "service.instance.id=pod-abc" in env["OTEL_RESOURCE_ATTRIBUTES"]
    assert "k8s.pod.name=pod-abc" in env["OTEL_RESOURCE_ATTRIBUTES"]
    assert notes["feature_inject.otlp_traces"] == "endpoint=collector:4317"
    assert notes["feature_inject.otlp_traces.vllm"] == "otlp_traces_endpoint"


def test_otlp_sglang(monkeypatch) -> None:
    """验证 SGLang 开 EnableTrace → 注入 enable_trace + otlp_traces_endpoint + SGLANG_TRACE_LEVEL。"""
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", "jaeger:4317")
    monkeypatch.setenv("HOSTNAME", "pod-xyz")
    override, env, notes = _inject_otlp_traces({"enable_otlp_traces": True}, "sglang")
    assert override == {"enable_trace": True, "otlp_traces_endpoint": "jaeger:4317"}
    assert env["OTEL_SERVICE_NAME"] == "sglang"
    assert env["SGLANG_TRACE_LEVEL"] == "2"
    assert env["OTEL_EXPORTER_OTLP_TRACES_INSECURE"] == "true"
    assert notes["feature_inject.otlp_traces.sglang"] == "enable_trace, otlp_traces_endpoint"


def test_otlp_default_endpoint(monkeypatch) -> None:
    """验证 OTLP_TRACES_ENDPOINT 未设置时使用默认 localhost:4317。"""
    monkeypatch.delenv("OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("HOSTNAME", "test-host")
    override, _, notes = _inject_otlp_traces({"enable_otlp_traces": True}, "vllm")
    assert override == {"otlp_traces_endpoint": "localhost:4317"}
    assert notes["feature_inject.otlp_traces"] == "endpoint=localhost:4317"


def test_otlp_unsupported_engine_skip(monkeypatch) -> None:
    """验证不支持的引擎 → skip,仅记录 notes。"""
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", "collector:4317")
    override, env, notes = _inject_otlp_traces({"enable_otlp_traces": True}, "mindie")
    assert not override
    # 通用 OTEL 环境变量仍会设置(不依赖引擎)
    assert env["OTEL_EXPORTER_OTLP_TRACES_INSECURE"] == "true"
    assert "feature_inject.otlp_traces.skip" in notes


def test_otlp_switch_off_is_noop() -> None:
    """验证开关未开 → no-op。"""
    override, env, notes = _inject_otlp_traces({}, "vllm")
    assert not override
    assert not env
    assert not notes


# ── _inject_metrics ───────────────────────────────────────────────────────


def test_rag_acc_enabled_injects_proxy_env() -> None:
    override, env, notes = _inject_rag_acc({"enable_rag_acc": True}, "vllm")
    assert not override
    assert env == {"RAG_ACC_ENABLED": "true"}
    assert notes["feature_inject.rag_acc"] == "enabled"


def test_rag_acc_explicitly_disabled_injects_proxy_env() -> None:
    override, env, notes = _inject_rag_acc({"enable_rag_acc": False}, "vllm")
    assert not override
    assert env == {"RAG_ACC_ENABLED": "false"}
    assert notes["feature_inject.rag_acc"] == "disabled"


def test_rag_acc_disabled_is_noop() -> None:
    override, env, notes = _inject_rag_acc({}, "vllm")
    assert not override
    assert not env
    assert not notes


def test_metrics_sglang() -> None:
    """验证 SGLang 开 Metrics → 注入 enable_metrics=True。"""
    override, env, notes = _inject_metrics({"enable_metrics": True}, "sglang")
    assert override == {"enable_metrics": True}
    assert not env
    assert notes["feature_inject.metrics"] == "enabled"
    assert notes["feature_inject.metrics.sglang"] == "enable_metrics"


def test_metrics_vllm_default_on() -> None:
    """验证 vLLM 开 Metrics → 无注入(默认开启),notes 标注 default_on, no_inject。"""
    override, env, notes = _inject_metrics({"enable_metrics": True}, "vllm")
    assert not override
    assert not env
    assert notes["feature_inject.metrics.vllm"] == "default_on, no_inject"


def test_metrics_vllm_ascend_default_on() -> None:
    """验证 vllm-ascend 与 vllm 共用 default_on 逻辑。"""
    override, _, notes = _inject_metrics({"enable_metrics": True}, "vllm-ascend")
    assert not override
    assert notes["feature_inject.metrics.vllm"] == "default_on, no_inject"


def test_metrics_unsupported_engine_skip() -> None:
    """验证不支持的引擎 → skip。"""
    override, _, notes = _inject_metrics({"enable_metrics": True}, "mindie")
    assert not override
    assert "feature_inject.metrics.skip" in notes


def test_metrics_switch_off_is_noop() -> None:
    """验证开关未开 → no-op。"""
    override, env, notes = _inject_metrics({}, "sglang")
    assert not override
    assert not env
    assert not notes


# ── feature_inject_transform(注册表汇总)─────────────────────────────────


def test_transform_all_switches_sglang(monkeypatch) -> None:
    """验证三开关同开 + SGLang → 合并 override/env/notes。"""
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", "collector:4317")
    monkeypatch.setenv("HOSTNAME", "pod-test")
    switches = {
        "enable_smartqos": True,
        "enable_otlp_traces": True,
        "enable_rag_acc": True,
        "enable_metrics": True,
    }
    override, env, notes = feature_inject_transform(switches, "sglang")

    # override 合并
    assert override["enable_priority_scheduling"] is True
    assert override["enable_trace"] is True
    assert override["otlp_traces_endpoint"] == "collector:4317"
    assert override["enable_metrics"] is True

    # env 合并
    assert env["OTEL_SERVICE_NAME"] == "sglang"
    assert env["SGLANG_TRACE_LEVEL"] == "2"
    assert env["OTEL_EXPORTER_OTLP_TRACES_INSECURE"] == "true"
    assert env["RAG_ACC_ENABLED"] == "true"

    # notes 合并(各特性键都在)
    assert "feature_inject.smartqos" in notes
    assert "feature_inject.otlp_traces" in notes
    assert "feature_inject.rag_acc" in notes
    assert "feature_inject.metrics" in notes


def test_transform_all_switches_vllm(monkeypatch) -> None:
    """验证三开关同开 + vLLM → 合并 override/env/notes。"""
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", "collector:4317")
    monkeypatch.setenv("HOSTNAME", "pod-test")
    switches = {
        "enable_smartqos": True,
        "enable_otlp_traces": True,
        "enable_rag_acc": True,
        "enable_metrics": True,
    }
    override, env, notes = feature_inject_transform(switches, "vllm")

    assert override["scheduling_policy"] == "priority"
    assert override["otlp_traces_endpoint"] == "collector:4317"
    # vLLM metrics default_on → 不在 override
    assert "enable_metrics" not in override
    assert env["OTEL_SERVICE_NAME"] == "vllm-server"
    assert env["RAG_ACC_ENABLED"] == "true"
    assert notes["feature_inject.rag_acc"] == "enabled"
    assert notes["feature_inject.metrics.vllm"] == "default_on, no_inject"


def test_transform_no_switches_is_noop() -> None:
    """验证无开关 → no-op(空 override/env/notes)。"""
    override, env, notes = feature_inject_transform({}, "vllm")
    assert not override
    assert not env
    assert not notes


def test_transform_partial_switches(monkeypatch) -> None:
    """验证仅开 SmartQoS → 只注入 SmartQoS,其余特性不触发。"""
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", "collector:4317")
    override, env, notes = feature_inject_transform({"enable_smartqos": True}, "sglang")
    assert override == {
        "enable_priority_scheduling": True,
        "schedule_low_priority_values_first": True,
        "priority_scheduling_preemption_threshold": 20,
    }
    # EnableTrace 未开 → 无 OTEL env
    assert "OTEL_SERVICE_NAME" not in env
    # Metrics 未开 → 无 metrics notes
    assert "feature_inject.metrics" not in notes
    assert "feature_inject.smartqos" in notes


def test_transform_unsupported_engine_all_skip(monkeypatch) -> None:
    """验证不支持的引擎 + 三开关同开 → 全部 skip,仅通用 OTEL env + notes。"""
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", "collector:4317")
    monkeypatch.setenv("HOSTNAME", "pod-test")
    switches = {
        "enable_smartqos": True,
        "enable_otlp_traces": True,
        "enable_metrics": True,
    }
    override, env, notes = feature_inject_transform(switches, "mindie")
    assert not override
    # 通用 OTEL 环境变量仍设置(不依赖引擎)
    assert env["OTEL_EXPORTER_OTLP_TRACES_INSECURE"] == "true"
    # 三个特性都记录 skip
    assert "feature_inject.smartqos.skip" in notes
    assert "feature_inject.otlp_traces.skip" in notes
    assert "feature_inject.metrics.skip" in notes
