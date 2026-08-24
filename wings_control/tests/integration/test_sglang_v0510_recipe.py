"""SGLang v0.5.10 Ascend recipe regression tests."""

from __future__ import annotations

import json

import pytest

from wings_ctl.core.config_resolver import resolve_config
from wings_ctl.core.models import ClusterPlacement, ResolvedEnv, Target, UserInput
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.validators.engine_param_validator import validate_engine_params


def test_sglang_v0510_qwen3_32b_single_node_recipe(config_root_real, tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    hardware_file = tmp_path / "hardware.json"
    hardware_file.write_text(
        json.dumps(
            {
                "hardware_family": "ascend-a3",
                "device": "ascend",
                "count": 16,
            }
        ),
        encoding="utf-8",
    )
    hardware = resolve_hardware(hardware_file)
    version = resolve_engine_version(config_root_real, hardware.hardware_family, engine="sglang")
    assert version.resolved == "v0.5.10"
    assert version.is_fallback is False

    resolved = resolve_config(
        ResolvedEnv(
            config_root=config_root_real,
            hardware=hardware,
            engine_version=version,
        ),
        Target(
            model_name="Qwen3-32B",
            topology=Topology.STANDALONE,
            engine="sglang",
        ),
        user_input=UserInput(cli_overrides={"model": "/models/Qwen3-32B"}),
        device_count=16,
    )

    traces = resolved.engine_config_traces
    assert "enable_dp_attention" not in traces
    assert traces["tp_size"].final_value == 4
    assert traces["dp_size"].final_value == 4
    argv = build_argv(traces, engine="sglang")
    assert argv[:5] == ["python3", "-m", "sglang.launch_server", "--model-path", "/models/Qwen3-32B"]
    assert argv[argv.index("--tp-size") + 1] == "4"
    assert argv[argv.index("--dp-size") + 1] == "4"
    assert argv[argv.index("--attention-backend") + 1] == "ascend"
    assert argv[argv.index("--device") + 1] == "npu"
    assert "--enable-dp-attention" not in argv
    assert {key: trace.final_value for key, trace in resolved.env_traces.items()} == {
        "SGLANG_SET_CPU_AFFINITY": 1,
        "PYTORCH_NPU_ALLOC_CONF": "expandable_segments:True",
        "STREAMS_PER_DEVICE": 32,
        "HCCL_BUFFSIZE": 1536,
        "HCCL_OP_EXPANSION_MODE": "AIV",
    }


def test_sglang_v0510_default_model_two_node_recipe(config_root_real, tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    hardware_file = tmp_path / "hardware.json"
    hardware_file.write_text(
        json.dumps(
            {
                "hardware_family": "ascend-a3",
                "device": "ascend",
                "count": 16,
            }
        ),
        encoding="utf-8",
    )
    hardware = resolve_hardware(hardware_file)
    version = resolve_engine_version(config_root_real, hardware.hardware_family, engine="sglang")

    for rank_ip, expected_rank in (
        ("10.0.0.1", 0),
        ("10.0.0.2", 1),
    ):
        resolved = resolve_config(
            ResolvedEnv(
                config_root=config_root_real,
                hardware=hardware,
                engine_version=version,
            ),
            Target(
                model_name="not-in-delivery-list",
                topology=Topology.MULTI_NODE,
                engine="sglang",
            ),
            user_input=UserInput(cli_overrides={"model": "/models/default"}),
            device_count=16,
            placement=ClusterPlacement(
                rank_ip=rank_ip,
                node_ips=["10.0.0.1", "10.0.0.2"],
                master_ip="10.0.0.1",
            ),
        )

        traces = resolved.engine_config_traces
        assert traces["tp_size"].final_value == 32
        assert "dp_size" not in traces
        assert "enable_dp_attention" not in traces
        assert "quantization" not in traces
        assert traces["nnodes"].final_value == 2
        assert traces["node_rank"].final_value == expected_rank
        assert traces["host"].final_value == "0.0.0.0"
        assert traces["dist_init_addr"].final_value == "10.0.0.1:5000"
        assert traces["dist_init_addr"].final_layer == "strategy_topology_inject"
        assert resolved.resolution_notes["multinode_dp_world_size"] == "32"
        assert resolved.resolution_notes["multinode_dp_resolved_dp"] == "1"

        argv = build_argv(traces, engine="sglang")
        assert argv[:5] == [
            "python3",
            "-m",
            "sglang.launch_server",
            "--model-path",
            "/models/default",
        ]
        assert argv[argv.index("--tp-size") + 1] == "32"
        assert argv[argv.index("--nnodes") + 1] == "2"
        assert argv[argv.index("--node-rank") + 1] == str(expected_rank)
        assert argv[argv.index("--dist-init-addr") + 1] == "10.0.0.1:5000"
        assert "--dp-size" not in argv
        assert "--enable-dp-attention" not in argv
        assert not any(marker in token for token in argv for marker in ("HEAD_IP", "local_ip", "MODEL_PATH"))

    with pytest.raises(ValueError, match="2 distinct Pods"):
        resolve_config(
            ResolvedEnv(
                config_root=config_root_real,
                hardware=hardware,
                engine_version=version,
            ),
            Target(
                model_name="not-in-delivery-list",
                topology=Topology.MULTI_NODE,
                engine="sglang",
            ),
            user_input=UserInput(cli_overrides={"model": "/models/default"}),
            device_count=16,
            placement=ClusterPlacement(
                rank_ip="10.0.0.1",
                node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"],
                master_ip="10.0.0.1",
            ),
        )


@pytest.mark.parametrize(
    (
        "hardware_family",
        "model_name",
        "topology",
        "device_count",
        "expected_tp",
        "expected_dp",
        "tool_calling",
    ),
    [
        ("rtx_pro_5000_72G", "Qwen3-32B", Topology.STANDALONE, 8, 2, 4, False),
        ("h20_141G", "DeepSeek-V3.1", Topology.STANDALONE, 8, 8, 1, True),
        ("l20_48G", "Qwen3-32B", Topology.MULTI_NODE, 4, 8, 1, False),
        ("rtx_pro_5000_72G", "Qwen3-32B", Topology.MULTI_NODE, 8, 16, 1, False),
        ("h20_141G", "Qwen3-32B", Topology.MULTI_NODE, 8, 16, 1, False),
    ],
    ids=[
        "single-rtx-pro-5000-qwen3-32b",
        "single-h20-deepseek-v3-1",
        "two-node-l20-qwen3-32b",
        "two-node-rtx-pro-5000-qwen3-32b",
        "two-node-h20-qwen3-32b",
    ],
)
def test_sglang_v0510_nvidia_delivery_recipes(
    config_root_real,
    tmp_path,
    monkeypatch,
    hardware_family,
    model_name,
    topology,
    device_count,
    expected_tp,
    expected_dp,
    tool_calling,
):
    """验证首期 NVIDIA 交付 recipe 的最终 argv、并行度和参数白名单。"""
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    monkeypatch.setattr("wings_ctl.core.config_resolver.resolve_weight_bytes", lambda _: 32 * 2**30)
    monkeypatch.setattr("wings_ctl.core.config_resolver.read_num_attention_heads", lambda _: 32)
    hardware_file = tmp_path / f"{hardware_family}.json"
    hardware_file.write_text(
        json.dumps(
            {
                "hardware_family": hardware_family,
                "device": "nvidia",
                "count": device_count,
            }
        ),
        encoding="utf-8",
    )
    hardware = resolve_hardware(hardware_file)
    version = resolve_engine_version(config_root_real, hardware.hardware_family, engine="sglang")
    placements = [None]
    if topology is Topology.MULTI_NODE:
        placements = [
            ClusterPlacement("10.0.0.1", ["10.0.0.1", "10.0.0.2"], "10.0.0.1"),
            ClusterPlacement("10.0.0.2", ["10.0.0.1", "10.0.0.2"], "10.0.0.1"),
        ]

    for expected_rank, placement in enumerate(placements):
        feature_switches = {"enable_auto_tool_choice": True} if tool_calling else {}
        resolved = resolve_config(
            ResolvedEnv(config_root_real, hardware, version),
            Target(model_name, topology, "sglang"),
            UserInput(
                cli_overrides={
                    "model": f"/models/{model_name}",
                    "port": 17000,
                    "served_model_name": model_name,
                },
                feature_switches=feature_switches,
            ),
            device_count=device_count,
            placement=placement,
        )
        validate_engine_params(resolved, config_root_real)

        traces = resolved.engine_config_traces
        argv = build_argv(traces, engine="sglang")
        actual_dp = traces["dp_size"].final_value if "dp_size" in traces else 1
        assert argv[:5] == ["python3", "-m", "sglang.launch_server", "--model-path", f"/models/{model_name}"]
        assert argv.count("--model-path") == 1
        assert traces["port"].final_value == 17000
        assert traces["tp_size"].final_value == expected_tp
        assert actual_dp == expected_dp
        assert "enable_dp_attention" not in traces
        assert resolved.param_validation is not None
        assert resolved.param_validation.unsupported == []

        if topology is Topology.MULTI_NODE:
            assert "pp_size" not in traces
            assert traces["nnodes"].final_value == 2
            assert traces["node_rank"].final_value == expected_rank
            assert traces["dist_init_addr"].final_value == "10.0.0.1:28030"
            assert traces["dist_init_addr"].final_layer == "strategy_topology_inject"
        if tool_calling:
            assert traces["tool_call_parser"].final_value == "deepseekv3"
