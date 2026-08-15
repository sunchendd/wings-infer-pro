from __future__ import annotations

from pathlib import Path

from wings_ctl.core import config_resolver
from wings_ctl.core.models import SourceEvent, TracedValue
from wings_ctl.loaders.reasoning_table import LoadedReasoningTable
from wings_ctl.strategy.post_merge import apply_post_merge_strategy
from wings_ctl.strategy.reasoning_resolver import ReasoningResolution, ReasoningSpec


def _traced(value, key="test") -> TracedValue:
    return TracedValue(
        final_value=value,
        final_layer="model_scenario",
        source_file="model.yaml",
        source_path=key,
        events=[SourceEvent("set", "model_scenario", value, "model.yaml", key)],
    )


def test_tp_dependent_ascend_params_are_removed_when_tp_is_one() -> None:
    result = apply_post_merge_strategy(
        {
            "tensor_parallel_size": _traced(1, "tensor_parallel_size"),
            "additional_config": _traced(
                {"enable_dsa_cp": True, "enable_cpu_binding": True},
                "additional_config",
            ),
        },
        {"VLLM_ASCEND_ENABLE_FLASHCOMM1": _traced(1), "TASK_QUEUE_ENABLE": _traced(1)},
        engine="vllm-ascend",
    )

    assert "VLLM_ASCEND_ENABLE_FLASHCOMM1" not in result.env_traces
    assert result.engine_config_traces["additional_config"].final_value == {"enable_cpu_binding": True}
    additional_config_trace = result.engine_config_traces["additional_config"]
    assert "enable_dsa_cp" not in additional_config_trace.final_value
    assert additional_config_trace.final_layer == "strategy_post_merge"
    assert additional_config_trace.events[-1] == SourceEvent(
        "remove",
        "strategy_post_merge",
        None,
        "<strategy:post_merge>",
        "additional_config.enable_dsa_cp",
    )
    assert result.notes["post_merge_tp_dependent.status"] == "removed"


def test_tp_dependent_ascend_params_are_removed_when_tp_is_absent() -> None:
    result = apply_post_merge_strategy(
        {"additional_config": _traced({"enable_dsa_cp": True})},
        {"VLLM_ASCEND_ENABLE_FLASHCOMM1": _traced(1)},
        engine="vllm-ascend",
    )

    assert "additional_config" not in result.engine_config_traces
    assert not result.env_traces


def test_tp_dependent_ascend_params_are_kept_when_tp_is_at_least_two() -> None:
    result = apply_post_merge_strategy(
        {
            "tensor_parallel_size": _traced(2, "tensor_parallel_size"),
            "additional_config": _traced({"enable_dsa_cp": True}),
        },
        {"VLLM_ASCEND_ENABLE_FLASHCOMM1": _traced(1)},
        engine="vllm-ascend",
    )

    assert result.engine_config_traces["additional_config"].final_value == {"enable_dsa_cp": True}
    assert "VLLM_ASCEND_ENABLE_FLASHCOMM1" in result.env_traces


def test_model_yaml_reasoning_takes_precedence(monkeypatch) -> None:
    loaded = LoadedReasoningTable({"architectures": []}, "/public/reason_parser.yaml")
    resolve_called = False

    def fail_resolve(*args, **kwargs):
        nonlocal resolve_called
        resolve_called = True
        raise AssertionError("public table must not override model YAML reasoning")

    monkeypatch.setattr(config_resolver, "load_reasoning_table", lambda _: loaded)
    monkeypatch.setattr(config_resolver, "resolve_reasoning", fail_resolve)

    features, result, source = config_resolver._prepare_feature_context(
        Path("/config"),
        "Qwen3",
        "vllm",
        {
            "features": {
                "reasoning": {"args": ["--reasoning-parser", "local_parser"]},
                "tool_calling": {"args": ["--tool-call-parser", "qwen3"]},
            },
        },
        True,
    )

    assert features["reasoning"] == {"args": ["--reasoning-parser", "local_parser"]}
    assert features["tool_calling"]["args"] == ["--tool-call-parser", "qwen3"]
    assert result is None
    assert source == ""
    assert not resolve_called


def test_public_table_is_used_when_model_yaml_has_no_reasoning(monkeypatch) -> None:
    loaded = LoadedReasoningTable({"architectures": []}, "/public/reason_parser.yaml")
    resolution = ReasoningResolution(
        "matched",
        ReasoningSpec(
            ("--reasoning-parser", "public_parser"),
            "architectures[0].models.Qwen3.vllm",
        ),
        loaded.source_path,
        "model",
    )
    monkeypatch.setattr(config_resolver, "load_reasoning_table", lambda _: loaded)
    monkeypatch.setattr(config_resolver, "resolve_reasoning", lambda *args, **kwargs: resolution)

    features, result, source = config_resolver._prepare_feature_context(
        Path("/config"),
        "Qwen3",
        "vllm",
        {"features": {"tool_calling": {"args": ["--tool-call-parser", "qwen3"]}}},
        True,
    )

    assert features["reasoning"] == {"args": ["--reasoning-parser", "public_parser"]}
    assert features["tool_calling"]["args"] == ["--tool-call-parser", "qwen3"]
    assert result is resolution
    assert source == loaded.source_path


def test_reasoning_feature_is_not_loaded_when_switch_is_disabled(monkeypatch) -> None:
    def fail_load(_):
        raise AssertionError("public reasoning table must not be loaded")

    monkeypatch.setattr(config_resolver, "load_reasoning_table", fail_load)
    features, result, source = config_resolver._prepare_feature_context(
        Path("/config"),
        "Qwen3",
        "vllm",
        {"features": {"reasoning": {"args": ["--reasoning-parser", "local_parser"]}}},
        False,
    )

    assert features["reasoning"] == {"args": ["--reasoning-parser", "local_parser"]}
    assert result is None
    assert source == ""
