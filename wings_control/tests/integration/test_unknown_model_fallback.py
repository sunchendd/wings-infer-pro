"""Unknown-model fallback tests for standalone dry-run resolution."""

from __future__ import annotations

import json
import os
import tempfile

from wings_ctl.core.config_resolver import resolve_config
from wings_ctl.core.models import ResolvedEnv, Target, UserInput
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.hardware.resolver import resolve_hardware


def _resolve_unknown(
    config_root_real,
    hardware_info_path,
    user_input=UserInput(),
    topology=Topology.STANDALONE,
):
    os.environ["ENGINE_VERSION"] = "0.19.0"
    try:
        hardware_info = json.loads(hardware_info_path.read_text())
        hardware_info["hardware_family"] = "h100"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as hardware_file:
            json.dump(hardware_info, hardware_file)
            hardware_file.flush()
            hardware = resolve_hardware(hardware_file.name)
        engine_version = resolve_engine_version(
            config_root_real, hardware.hardware_family, engine="vllm"
        )
        return resolve_config(
            ResolvedEnv(
                config_root=config_root_real,
                hardware=hardware,
                engine_version=engine_version,
            ),
            Target(
                model_name="Nonexistent-DryRun-Test-0.8B",
                topology=topology,
                engine="vllm",
            ),
            user_input,
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
