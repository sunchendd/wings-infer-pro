"""Unknown-model fallback tests for standalone dry-run resolution."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from wings_ctl.audit.emitter import emit_audit
from wings_ctl.audit.startup_log import _build_summary_lines
from wings_ctl.core.config_resolver import resolve_config
from wings_ctl.core.models import ClusterPlacement, ResolvedEnv, Target, UserInput
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.hardware.resolver import resolve_hardware


def _resolve_unknown(
    config_root_real,
    hardware_info_path,
    user_input=UserInput(),
    topology=Topology.STANDALONE,
    hardware_family="h100",
    device_count=None,
    placement=None,
    *,
    engine="vllm",
    engine_version="0.19.0",
    device=None,
    model_name="Nonexistent-DryRun-Test-0.8B",
):
    os.environ["ENGINE_VERSION"] = engine_version
    try:
        hardware_info = json.loads(hardware_info_path.read_text(encoding="utf-8"))
        hardware_info["hardware_family"] = hardware_family
        if device is not None:
            hardware_info["device"] = device
        fd, hardware_file = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            with open(hardware_file, "w", encoding="utf-8") as stream:
                json.dump(hardware_info, stream)
            hardware = resolve_hardware(hardware_file)
        finally:
            os.unlink(hardware_file)
        resolved_version = resolve_engine_version(
            config_root_real, hardware.hardware_family, engine=engine
        )
        return resolve_config(
            ResolvedEnv(
                config_root=config_root_real,
                hardware=hardware,
                engine_version=resolved_version,
            ),
            Target(
                model_name=model_name,
                topology=topology,
                engine=engine,
            ),
            user_input,
            device_count=device_count,
            placement=placement,
        )
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def test_unknown_model_uses_requested_name_as_engine_model(
    config_root_real, hardware_info_path
):
    resolved = _resolve_unknown(config_root_real, hardware_info_path)

    assert resolved.engine_config_traces["model"].final_value == (
        "Nonexistent-DryRun-Test-0.8B"
    )
    argv = build_argv(resolved.engine_config_traces, engine="vllm")
    assert argv[0:3] == ["vllm", "serve", "Nonexistent-DryRun-Test-0.8B"]
    assert "--host" in argv


def test_explicit_model_path_overrides_unknown_model_fallback(
    config_root_real, hardware_info_path
):
    resolved = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        UserInput(cli_overrides={"model_path": "/models/custom"}),
    )

    assert resolved.engine_config_traces["model_path"].final_value == "/models/custom"
    assert "model" not in resolved.engine_config_traces
    argv = build_argv(resolved.engine_config_traces, engine="vllm")
    assert argv[0:3] == ["vllm", "serve", "/models/custom"]


def test_unknown_hardware_and_model_use_generic_standalone_fallback(
    config_root_real, hardware_info_path, tmp_path
):
    resolved = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        hardware_family="NonExistentCard_99G",
    )

    assert resolved.resolution_notes["hardware_fallback"] is True
    assert resolved.resolution_notes["resolved_hardware_family"] == "_generic"
    assert resolved.resolution_notes["fallback"] is True
    assert "/_generic/models/default_model.yaml" in resolved.resolution_notes["matched_model_yaml"].replace("\\", "/")
    model_trace = resolved.engine_config_traces["model"]
    assert model_trace.final_value == "Nonexistent-DryRun-Test-0.8B"
    assert model_trace.final_layer == "request_default"
    assert model_trace.source_file == "<request>"
    assert model_trace.source_path == "request.model"
    assert resolved.engine_config_traces["max_model_len"].source_path == (
        "scenarios.standalone.strategies.generic.engine_config.max_model_len"
    )

    audit = json.loads(emit_audit(resolved, tmp_path).read_text(encoding="utf-8"))
    assert audit["resolution_notes"]["hardware_fallback"] is True
    assert audit["resolution_notes"]["resolved_hardware_family"] == "_generic"
    assert audit["engine_config"]["model"]["source_file"] == "<request>"
    assert audit["engine_config"]["model"]["source_path"] == "request.model"

    summary = _build_summary_lines(
        resolved,
        {
            "start": tmp_path / "start_command.sh",
            "repro": tmp_path / "repro.sh",
            "audit": tmp_path / "audit.json",
            "model_name": "Nonexistent-DryRun-Test-0.8B",
        },
        tmp_path / "wings_start.log",
    )
    assert "used generic best-effort recipe=_generic" in summary
    assert "engine=vllm device=nvidia" in summary
    assert "caller is responsible for engine/device compatibility" in summary
    assert "device_count=unset -> keeping generic template TP=1, DP=1" in summary


@pytest.mark.parametrize(
    ("engine", "engine_version", "device", "tp_key", "dp_flag"),
    [
        ("vllm", "0.19.0", "nvidia", "tensor_parallel_size", "--data-parallel-size"),
        ("vllm-ascend", "v0.18.0", "ascend", "tensor_parallel_size", "--data-parallel-size"),
        ("sglang", "v0.5.10", "ascend", "tp_size", "--dp-size"),
    ],
)
def test_generic_standalone_uses_all_devices_as_one_tp_group(
    config_root_real,
    hardware_info_path,
    engine,
    engine_version,
    device,
    tp_key,
    dp_flag,
    tmp_path,
):
    resolved = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        hardware_family="UnknownHardware_99G",
        device_count=8,
        engine=engine,
        engine_version=engine_version,
        device=device,
    )

    tp_trace = resolved.engine_config_traces[tp_key]
    assert tp_trace.final_value == 8
    assert tp_trace.final_layer == "strategy_generic_fallback"
    assert tp_trace.source_file == "<strategy:generic_fallback>"
    assert tp_trace.source_path == f"strategy.generic_fallback.{tp_key}"
    assert [event.layer for event in tp_trace.events] == ["default_model", "strategy_generic_fallback"]
    assert resolved.resolution_notes["generic_fallback_resolved_tp"] == "8"
    assert resolved.resolution_notes["generic_fallback_resolved_dp"] == "1"

    argv = build_argv(resolved.engine_config_traces, engine=engine)
    assert dp_flag not in argv
    assert "data_parallel_size" not in resolved.engine_config_traces
    assert "dp_size" not in resolved.engine_config_traces

    audit = json.loads(emit_audit(resolved, tmp_path).read_text(encoding="utf-8"))
    audit_tp = audit["engine_config"][tp_key]
    assert audit_tp["final_layer"] == "strategy_generic_fallback"
    assert [event["layer"] for event in audit_tp["events"]] == [
        "default_model",
        "strategy_generic_fallback",
    ]

    summary = _build_summary_lines(
        resolved,
        {
            "start": tmp_path / "start_command.sh",
            "repro": tmp_path / "repro.sh",
            "audit": tmp_path / "audit.json",
            "model_name": "Nonexistent-DryRun-Test-0.8B",
        },
        tmp_path / "wings_start.log",
    )
    assert "device_count=8 -> TP=8, DP=1 (strategy_generic_fallback, status=tp_from_device_count)" in summary


def test_generic_standalone_without_device_count_keeps_template_and_warns(
    config_root_real, hardware_info_path, caplog
):
    with caplog.at_level("WARNING"):
        resolved = _resolve_unknown(
            config_root_real,
            hardware_info_path,
            hardware_family="UnknownHardware_99G",
        )

    tp_trace = resolved.engine_config_traces["tensor_parallel_size"]
    assert tp_trace.final_value == 1
    assert tp_trace.final_layer == "default_model"
    assert resolved.resolution_notes["generic_fallback_parallelism_status"] == "template_no_device_count"
    assert resolved.resolution_notes["generic_fallback_resolved_tp"] == "1"
    assert resolved.resolution_notes["generic_fallback_resolved_dp"] == "1"
    assert "Generic hardware fallback has no device-count" in caplog.text


def test_generic_standalone_user_parallelism_still_wins(
    config_root_real, hardware_info_path
):
    resolved = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        UserInput(cli_overrides={"tensor_parallel_size": 4, "data_parallel_size": 2}),
        hardware_family="UnknownHardware_99G",
        device_count=8,
    )

    assert resolved.engine_config_traces["tensor_parallel_size"].final_value == 4
    assert resolved.engine_config_traces["tensor_parallel_size"].final_layer == "user_cli"
    assert resolved.engine_config_traces["data_parallel_size"].final_value == 2
    assert resolved.engine_config_traces["data_parallel_size"].final_layer == "user_cli"


def test_unknown_hardware_disables_smart_accel(
    config_root_real, hardware_info_path, monkeypatch
):
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")

    resolved = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        hardware_family="NonExistentCard_99G",
    )

    assert resolved.accel.enabled is False
    assert resolved.resolution_notes["accel_policy"] == "disabled_generic_hardware_fallback"
    assert resolved.resolution_notes["accel_dropped_switches"] == "ENABLE_SPECULATIVE_DECODE"


def test_unknown_hardware_multi_node_uses_generic_node_templates(
    config_root_real, hardware_info_path
):
    resolved = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        topology=Topology.MULTI_NODE,
        hardware_family="NonExistentCard_99G",
    )

    assert resolved.resolution_notes["hardware_fallback"] is True
    assert resolved.nodes is not None
    assert [node.role for node in resolved.nodes] == ["head", "worker"]
    assert all("node_rank" in node.engine_config_traces for node in resolved.nodes)
    assert all(
        node.engine_config_traces["tensor_parallel_size"].final_value == 2
        for node in resolved.nodes
    )
    generic_yaml = str(
        config_root_real / "engines" / "vllm" / "_generic" / "models" / "default_model.yaml"
    )
    assert resolved.nodes[0].engine_config_traces["nnodes"].final_layer == "default_model"
    assert resolved.nodes[0].engine_config_traces["nnodes"].source_file == generic_yaml
    assert resolved.nodes[0].engine_config_traces["nnodes"].source_path == (
        "scenarios.multi_node.strategies.generic.head.engine_config.nnodes"
    )
    assert resolved.nodes[1].engine_config_traces["headless"].final_layer == "default_model"
    assert resolved.nodes[1].engine_config_traces["headless"].source_file == generic_yaml
    assert resolved.nodes[1].engine_config_traces["headless"].source_path == (
        "scenarios.multi_node.strategies.generic.worker.engine_config.headless"
    )
    assert all(
        node.engine_config_traces["model"].final_layer == "request_default"
        and node.engine_config_traces["model"].source_file == "<request>"
        and node.engine_config_traces["model"].source_path == "request.model"
        for node in resolved.nodes
    )


def test_generic_fallback_warns_without_rejecting_engine_device_mismatch(
    config_root_real, hardware_info_path, caplog
):
    with caplog.at_level("WARNING"):
        resolved = _resolve_unknown(
            config_root_real,
            hardware_info_path,
            hardware_family="NonExistentCard_99G",
            engine="vllm-ascend",
            engine_version="v0.18.0",
            device="nvidia",
        )

    assert resolved.resolution_notes["hardware_fallback"] is True
    assert "engine='vllm-ascend' device='nvidia'" in caplog.text
    assert "caller is responsible for engine/device compatibility" in caplog.text


def test_unknown_hardware_multi_node_runtime_uses_existing_topology_injection(
    config_root_real, hardware_info_path
):
    resolved = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        topology=Topology.MULTI_NODE,
        hardware_family="NonExistentCard_99G",
        placement=ClusterPlacement(
            rank_ip="10.0.0.2",
            node_ips=["10.0.0.1", "10.0.0.2"],
            master_ip="10.0.0.1",
        ),
    )

    assert resolved.nodes is None
    assert resolved.resolution_notes["hardware_fallback"] is True
    assert resolved.resolution_notes["multi_node_index"] == "1"
    assert resolved.engine_config_traces["tensor_parallel_size"].final_value == 2
    assert resolved.engine_config_traces["node_rank"].final_value == 1
    assert resolved.engine_config_traces["master_addr"].final_value == "10.0.0.1"
    generic_yaml = str(
        config_root_real / "engines" / "vllm" / "_generic" / "models" / "default_model.yaml"
    )
    max_len_trace = resolved.engine_config_traces["max_model_len"]
    assert max_len_trace.final_layer == "default_model"
    assert max_len_trace.source_file == generic_yaml
    assert max_len_trace.source_path == (
        "scenarios.multi_node.strategies.generic.worker.engine_config.max_model_len"
    )
    model_trace = resolved.engine_config_traces["model"]
    assert model_trace.final_layer == "request_default"
    assert model_trace.source_file == "<request>"
    assert model_trace.source_path == "request.model"


def test_vllm_ascend_generic_fallback_standalone_and_runtime_two_node(
    config_root_real, hardware_info_path
):
    standalone = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        hardware_family="UnknownAscend_99G",
        engine="vllm-ascend",
        engine_version="v0.18.0",
        device="ascend",
    )
    standalone_argv = build_argv(standalone.engine_config_traces, engine="vllm-ascend")
    assert standalone.engine_version.requested == "v0.18.0"
    assert standalone.engine_version.resolved == "v0.18.0"
    assert standalone.resolution_notes["hardware_fallback"] is True
    assert standalone.engine_config_traces["tensor_parallel_size"].final_value == 1
    assert standalone_argv[:3] == ["vllm", "serve", "Nonexistent-DryRun-Test-0.8B"]
    assert "--tensor-parallel-size" in standalone_argv

    runtime = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        topology=Topology.MULTI_NODE,
        hardware_family="UnknownAscend_99G",
        placement=ClusterPlacement(
            rank_ip="10.0.0.2",
            node_ips=["10.0.0.1", "10.0.0.2"],
            master_ip="10.0.0.1",
        ),
        engine="vllm-ascend",
        engine_version="v0.18.0",
        device="ascend",
    )
    runtime_argv = build_argv(runtime.engine_config_traces, engine="vllm-ascend")
    assert runtime.nodes is None
    assert runtime.engine_config_traces["tensor_parallel_size"].final_value == 2
    assert runtime.engine_config_traces["node_rank"].final_value == 1
    assert runtime.engine_config_traces["master_addr"].final_value == "10.0.0.1"
    assert "--tensor-parallel-size" in runtime_argv
    assert "2" in runtime_argv


def test_sglang_generic_fallback_standalone_and_runtime_two_node(
    config_root_real, hardware_info_path
):
    standalone = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        hardware_family="UnknownNpu_99G",
        engine="sglang",
        engine_version="v0.5.10",
        device="ascend",
    )
    standalone_argv = build_argv(standalone.engine_config_traces, engine="sglang")
    assert standalone.engine_version.requested == "v0.5.10"
    assert standalone.engine_version.resolved == "v0.5.10"
    assert standalone.resolution_notes["hardware_fallback"] is True
    assert standalone.engine_config_traces["tp_size"].final_value == 1
    assert standalone_argv[:5] == [
        "python3",
        "-m",
        "sglang.launch_server",
        "--model-path",
        "Nonexistent-DryRun-Test-0.8B",
    ]
    assert "--tp-size" in standalone_argv

    runtime = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        topology=Topology.MULTI_NODE,
        hardware_family="UnknownNpu_99G",
        placement=ClusterPlacement(
            rank_ip="10.0.0.2",
            node_ips=["10.0.0.1", "10.0.0.2"],
            master_ip="10.0.0.1",
        ),
        engine="sglang",
        engine_version="v0.5.10",
        device="ascend",
    )
    runtime_argv = build_argv(runtime.engine_config_traces, engine="sglang")
    assert runtime.nodes is None
    assert runtime.engine_config_traces["tp_size"].final_value == 2
    assert runtime.engine_config_traces["node_rank"].final_value == 1
    assert runtime.engine_config_traces["dist_init_addr"].final_value == "10.0.0.1:5000"
    assert "--tp-size" in runtime_argv
    assert "2" in runtime_argv


def test_specific_model_recipe_keeps_existing_device_count_strategy(
    config_root_real, hardware_info_path
):
    resolved = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        hardware_family="h100",
        device_count=16,
        model_name="DeepSeek-OCR-bf16",
    )

    assert resolved.resolution_notes["fallback"] is False
    assert "generic_fallback_parallelism_status" not in resolved.resolution_notes
    assert resolved.engine_config_traces["tensor_parallel_size"].final_value == 1
    assert resolved.engine_config_traces["data_parallel_size"].final_value == 16
    assert resolved.engine_config_traces["data_parallel_size"].final_layer == "strategy_device_count"


def test_unknown_model_multi_node_uses_platform_node_templates(
    config_root_real, hardware_info_path
):
    """未知模型的 multi_node fallback 仍按 default_model.yaml 展开 head/worker。"""
    resolved = _resolve_unknown(
        config_root_real,
        hardware_info_path,
        topology=Topology.MULTI_NODE,
    )

    assert resolved.nodes is not None
    assert [node.role for node in resolved.nodes] == ["head", "worker"]
    assert all(
        node.engine_config_traces["model"].final_value
        == "Nonexistent-DryRun-Test-0.8B"
        for node in resolved.nodes
    )
    head_argv = build_argv(resolved.nodes[0].engine_config_traces, engine="vllm")
    worker_argv = build_argv(resolved.nodes[1].engine_config_traces, engine="vllm")
    assert "--nnodes" in head_argv and "2" in head_argv
    assert "--node-rank" in head_argv and "0" in head_argv
    assert "--node-rank" in worker_argv and "1" in worker_argv
    assert "--headless" in worker_argv
