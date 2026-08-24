"""SGLang v0.5.10 首期交付边界回归测试。"""

from __future__ import annotations

import json
import shutil

import pytest

from wings_ctl.core.config_resolver import resolve_config, resolve_custom_config
from wings_ctl.core.models import ClusterPlacement, CustomConfigFile, ResolvedEnv, Target, UserInput
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware


def _env(config_root, tmp_path):
    hardware_file = tmp_path / "hardware.json"
    hardware_file.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    hardware = resolve_hardware(hardware_file)
    version = resolve_engine_version(config_root, hardware.hardware_family, engine="sglang")
    return ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=version)


def test_sglang_v0510_requires_prefixed_requested_version(config_root_real, tmp_path, monkeypatch):
    for requested in (None, "0.5.10", "v0.5.9", "v0.5.100"):
        if requested is None:
            monkeypatch.delenv("ENGINE_VERSION", raising=False)
        else:
            monkeypatch.setenv("ENGINE_VERSION", requested)
        with pytest.raises(ValueError, match="v0.5.10"):
            resolve_engine_version(config_root_real, "ascend-a3", engine="sglang")

    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10-build.1")
    version = resolve_engine_version(config_root_real, "ascend-a3", engine="sglang")
    assert version.resolved == "v0.5.10"
    assert version.is_fallback is False

    missing_root = tmp_path / "missing-config"
    with pytest.raises(FileNotFoundError, match="available version directory"):
        resolve_engine_version(missing_root, "ascend-a3", engine="sglang")


def test_sglang_v0510_rejects_unsupported_topology_and_uses_default_model(config_root_real, tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    env = _env(config_root_real, tmp_path)

    with pytest.raises(ValueError, match="does not support topology"):
        resolve_config(
            env,
            Target(model_name="Qwen3-32B", topology=Topology.PD_PREFILL, engine="sglang"),
        )

    fallback_root = tmp_path / "fallback-config"
    shutil.copytree(
        config_root_real / "engines" / "sglang" / "v0.5.10",
        fallback_root / "engines" / "sglang" / "v0.5.10",
    )
    default_model = fallback_root / "engines" / "sglang" / "v0.5.10" / "ascend-a3" / "models" / "default_model.yaml"
    default_model.write_text(
        "scenarios:\n"
        "  standalone:\n"
        "    engine_config:\n"
        "      model: $MODEL_PATH\n"
        "      tp_size: 16\n"
        "    env: {}\n"
        "    system_setup: {}\n",
        encoding="utf-8",
    )
    resolved = resolve_config(
        _env(fallback_root, tmp_path),
        Target(model_name="not-in-delivery-list", topology=Topology.STANDALONE, engine="sglang"),
        user_input=UserInput(cli_overrides={"model": "/models/default"}),
        device_count=16,
    )
    assert resolved.engine_config_traces["model"].final_value == "/models/default"
    assert resolved.engine_config_traces["tp_size"].final_layer == "default_model"
    assert "dp_size" not in resolved.engine_config_traces
    assert "data_parallel_size" not in resolved.engine_config_traces
    assert resolved.resolution_notes["fallback"] is True


def test_sglang_v0510_rejects_dpa_and_multinode_dp(config_root_real, tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    env = _env(config_root_real, tmp_path)

    with pytest.raises(ValueError, match="enable_dp_attention"):
        resolve_config(
            env,
            Target(model_name="Qwen3-32B", topology=Topology.STANDALONE, engine="sglang"),
            user_input=UserInput(cli_overrides={"model": "/models/Qwen3-32B", "enable_dp_attention": True}),
            device_count=16,
        )

    with pytest.raises(ValueError, match="Conflicting parallelism parameter aliases"):
        resolve_config(
            env,
            Target(
                model_name="Qwen3-32B",
                topology=Topology.STANDALONE,
                engine="sglang",
            ),
            user_input=UserInput(
                cli_overrides={
                    "model": "/models/Qwen3-32B",
                    "tensor_parallel_size": 8,
                }
            ),
            device_count=16,
        )

    with pytest.raises(ValueError, match="DP>1"):
        resolve_config(
            env,
            Target(model_name="not-in-delivery-list", topology=Topology.MULTI_NODE, engine="sglang"),
            user_input=UserInput(cli_overrides={"model": "/models/default", "dp_size": 2}),
            device_count=16,
            placement=ClusterPlacement(
                rank_ip="10.0.0.1",
                node_ips=["10.0.0.1", "10.0.0.2"],
                master_ip="10.0.0.1",
            ),
        )

    with pytest.raises(ValueError, match="node_rank=0.*Pod index 1"):
        resolve_config(
            env,
            Target(model_name="not-in-delivery-list", topology=Topology.MULTI_NODE, engine="sglang"),
            user_input=UserInput(cli_overrides={"model": "/models/default", "node_rank": 0}),
            device_count=16,
            placement=ClusterPlacement(
                rank_ip="10.0.0.2",
                node_ips=["10.0.0.1", "10.0.0.2"],
                master_ip="10.0.0.1",
            ),
        )


def test_sglang_v0510_drops_accel_switches(config_root_real, tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    monkeypatch.setenv("ENABLE_SPARSE", "true")
    env = _env(config_root_real, tmp_path)

    resolved = resolve_config(
        env,
        Target(model_name="Qwen3-32B", topology=Topology.STANDALONE, engine="sglang"),
        user_input=UserInput(cli_overrides={"model": "/models/Qwen3-32B"}),
        device_count=16,
    )

    assert resolved.accel.enabled is False
    assert resolved.resolution_notes["accel_policy"] == "drop_warn"
    assert resolved.resolution_notes["accel_dropped_switches"] == "ENABLE_SPARSE"
    assert "ignored switches: ENABLE_SPARSE" in caplog.text


def test_sglang_v0510_custom_config_obeys_delivery_boundary(config_root_real, tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    monkeypatch.setenv("ENABLE_SPARSE", "true")
    env = _env(config_root_real, tmp_path)

    resolved = resolve_custom_config(
        env,
        Target(model_name="Qwen3-32B", topology=Topology.STANDALONE, engine="sglang"),
        CustomConfigFile(params={"tp_size": 1}),
        user_input=UserInput(cli_overrides={"model": "/models/Qwen3-32B"}),
    )
    assert resolved.engine_config_traces["tensor_parallel_size"].final_value == 1
    assert resolved.accel.enabled is False
    assert resolved.resolution_notes["accel_policy"] == "drop_warn"

    with pytest.raises(ValueError, match="enable_dp_attention"):
        resolve_custom_config(
            env,
            Target(
                model_name="Qwen3-32B",
                topology=Topology.STANDALONE,
                engine="sglang",
            ),
            CustomConfigFile(params={"enable_dp_attention": True}),
            user_input=UserInput(cli_overrides={"model": "/models/Qwen3-32B"}),
        )


def test_sglang_v0510_requires_complete_runtime_placement(config_root_real, tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    env = _env(config_root_real, tmp_path)

    with pytest.raises(ValueError, match="NODE_IPS, RANK_IP and MASTER_IP together"):
        resolve_config(
            env,
            Target(model_name="not-in-delivery-list", topology=Topology.MULTI_NODE, engine="sglang"),
            user_input=UserInput(cli_overrides={"model": "/models/default"}),
            device_count=16,
            placement=ClusterPlacement(
                node_ips=["10.0.0.1", "10.0.0.2"],
                master_ip="10.0.0.1",
            ),
        )


def test_sglang_v0510_rejects_cli_rendezvous_override(config_root_real, tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    env = _env(config_root_real, tmp_path)

    with pytest.raises(ValueError, match="runtime dist_init_addr='10.0.0.1:5000'"):
        resolve_config(
            env,
            Target(model_name="not-in-delivery-list", topology=Topology.MULTI_NODE, engine="sglang"),
            user_input=UserInput(
                cli_overrides={
                    "model": "/models/default",
                    "dist_init_addr": "203.0.113.9:9999",
                }
            ),
            device_count=16,
            placement=ClusterPlacement(
                rank_ip="10.0.0.1",
                node_ips=["10.0.0.1", "10.0.0.2"],
                master_ip="10.0.0.1",
            ),
        )


def test_sglang_v0510_custom_multinode_requires_complete_world_tp(
    config_root_real,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    env = _env(config_root_real, tmp_path)
    placement = ClusterPlacement(
        rank_ip="10.0.0.1",
        node_ips=["10.0.0.1", "10.0.0.2"],
        master_ip="10.0.0.1",
    )

    with pytest.raises(ValueError, match="tp_size=32"):
        resolve_custom_config(
            env,
            Target(model_name="Qwen3-32B", topology=Topology.MULTI_NODE, engine="sglang"),
            CustomConfigFile(params={"tp_size": 1}),
            user_input=UserInput(cli_overrides={"model": "/models/Qwen3-32B"}),
            device_count=16,
            placement=placement,
        )


def test_sglang_v0510_custom_rejects_cli_rendezvous_override(
    config_root_real,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    env = _env(config_root_real, tmp_path)

    with pytest.raises(ValueError, match="runtime dist_init_addr='10.0.0.1:5000'"):
        resolve_custom_config(
            env,
            Target(model_name="Qwen3-32B", topology=Topology.MULTI_NODE, engine="sglang"),
            CustomConfigFile(params={"tp_size": 32}),
            user_input=UserInput(
                cli_overrides={
                    "model": "/models/Qwen3-32B",
                    "dist_init_addr": "203.0.113.9:9999",
                }
            ),
            device_count=16,
            placement=ClusterPlacement(
                rank_ip="10.0.0.1",
                node_ips=["10.0.0.1", "10.0.0.2"],
                master_ip="10.0.0.1",
            ),
        )


def test_sglang_v0510_rejects_fractional_parallelism(config_root_real, tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINE_VERSION", "v0.5.10")
    env = _env(config_root_real, tmp_path)

    with pytest.raises(ValueError, match="tp_size must be a positive integer"):
        resolve_config(
            env,
            Target(model_name="not-in-delivery-list", topology=Topology.MULTI_NODE, engine="sglang"),
            user_input=UserInput(cli_overrides={"model": "/models/default", "tp_size": 32.5}),
            device_count=16,
            placement=ClusterPlacement(
                rank_ip="10.0.0.1",
                node_ips=["10.0.0.1", "10.0.0.2"],
                master_ip="10.0.0.1",
            ),
        )
