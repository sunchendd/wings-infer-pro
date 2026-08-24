from __future__ import annotations

from pathlib import Path

from wings_ctl.core import config_resolver
from wings_ctl.core.models import SourceEvent, TracedValue
from wings_ctl.loaders.reasoning_table import LoadedReasoningTable
from wings_ctl.strategy.post_merge import apply_network_env_strategy, apply_post_merge_strategy
from wings_ctl.strategy.reasoning_resolver import ReasoningResolution, ReasoningSpec


def _traced(value, key="test") -> TracedValue:
    return TracedValue(
        final_value=value,
        final_layer="model_scenario",
        source_file="model.yaml",
        source_path=key,
        events=[SourceEvent("set", "model_scenario", value, "model.yaml", key)],
    )


def test_network_env_strategy_overrides_declared_keys_with_trace(monkeypatch) -> None:
    monkeypatch.setattr("wings_ctl.strategy.post_merge.get_local_ip", lambda: "10.0.0.2")
    monkeypatch.setattr("wings_ctl.strategy.post_merge.get_interface_for_ip", lambda _ip: ("ens5", True))
    result, notes = apply_network_env_strategy(
        {
            "HCCL_IF_IP": _traced("$local_ip", "env.HCCL_IF_IP"),
            "NETWORK_CARD_NAME": _traced("$nic_name", "env.NETWORK_CARD_NAME"),
            "GLOO_SOCKET_IFNAME": _traced("$nic_name", "env.GLOO_SOCKET_IFNAME"),
            "NCCL_SOCKET_IFNAME": _traced("$IFACE_NAME", "env.NCCL_SOCKET_IFNAME"),
            "OTHER": _traced("unchanged", "env.OTHER"),
        }
    )

    assert result["HCCL_IF_IP"].final_value == "10.0.0.2"
    assert result["NETWORK_CARD_NAME"].final_value == "ens5"
    assert result["GLOO_SOCKET_IFNAME"].final_value == "ens5"
    assert result["NCCL_SOCKET_IFNAME"].final_value == "ens5"
    assert result["OTHER"].final_value == "unchanged"
    assert result["HCCL_IF_IP"].events[-1] == SourceEvent(
        "override", "strategy_network_env", "10.0.0.2", "<strategy:network_env>", "get_local_ip"
    )
    assert result["NETWORK_CARD_NAME"].events[-1].source_path == "interface_for_local_ip:matched"
    assert result["GLOO_SOCKET_IFNAME"].events[-1].source_path == "interface_for_local_ip:matched"
    assert result["NCCL_SOCKET_IFNAME"].events[-1].source_path == "interface_for_local_ip:matched"
    assert notes["network_env_override.interface"] == "ens5"
    assert notes["network_env_override.keys"] == "HCCL_IF_IP,NETWORK_CARD_NAME,GLOO_SOCKET_IFNAME,NCCL_SOCKET_IFNAME"


def test_network_env_strategy_records_eth0_fallback(monkeypatch) -> None:
    monkeypatch.setattr("wings_ctl.strategy.post_merge.get_local_ip", lambda: "10.0.0.2")
    monkeypatch.setattr("wings_ctl.strategy.post_merge.get_interface_for_ip", lambda _ip: ("eth0", False))

    result, notes = apply_network_env_strategy({"HCCL_SOCKET_IFNAME": _traced("$nic_name")})

    assert result["HCCL_SOCKET_IFNAME"].final_value == "eth0"
    assert result["HCCL_SOCKET_IFNAME"].events[-1].source_path == "interface_for_local_ip:fallback_eth0"
    assert notes["network_env_override.interface_discovery"] == "fallback_eth0"


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

    features, result, source, _ = config_resolver._prepare_feature_context(
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

    features, result, source, _ = config_resolver._prepare_feature_context(
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
    features, result, source, _ = config_resolver._prepare_feature_context(
        Path("/config"),
        "Qwen3",
        "vllm",
        {"features": {"reasoning": {"args": ["--reasoning-parser", "local_parser"]}}},
        False,
    )

    assert features["reasoning"] == {"args": ["--reasoning-parser", "local_parser"]}
    assert result is None
    assert source == ""
