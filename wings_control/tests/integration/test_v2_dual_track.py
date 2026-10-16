"""v2 双轨路由集成测试（refactor.md §5）。

覆盖：v2 命中 → 用 v2 资产（resolution_notes.asset_source == 'v2'）；
v2 未命中 → 回退 v1（asset_source == 'v1'）。

注：本测试依赖完整 wings_ctl 流水线（fcntl），仅 Linux 可运行。
"""

from __future__ import annotations

import json
from pathlib import Path

from wings_ctl.core.config_resolver import resolve_config
from wings_ctl.core.models import ClusterPlacement, ResolvedEnv, Target, Topology, UserInput
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.hardware.resolver import resolve_hardware


def _write_hardware(tmp_path: Path, family: str) -> Path:
    hw = tmp_path / "hardware_info.json"
    hw.write_text(json.dumps({"hardware_family": family, "device": "ascend", "count": 16}), encoding="utf-8")
    return hw


def _make_env(config_root: Path, hw_path: Path) -> ResolvedEnv:
    hardware = resolve_hardware(hw_path)
    engine_version = resolve_engine_version(config_root, hardware.hardware_family, engine="vllm-ascend")
    return ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=engine_version)


def test_v2_hit_uses_v2_asset(config_root_real, tmp_path, monkeypatch):
    """v2 命中（DeepSeek-V4-Flash-w8a8-mtp 在 v2 资产树）→ asset_source == 'v2'。"""
    # 迁移资产声明 version v0.23.0 / hardware Ascend910C_64G。调用方以别名
    # Ascend910_64G 下发，经 hardware_table.yaml 归一化后命中。这里必须钉住版本：
    # 不钉时版本解析会落到 latest v1 目录（v0.26.0rc1），与 v2 资产前缀不匹配 → 回退 v1。
    monkeypatch.setenv("ENGINE_VERSION", "v0.23.0")
    hw = _write_hardware(tmp_path, "Ascend910_64G")
    env = _make_env(config_root_real, hw)
    target = Target(model_name="DeepSeek-V4-Flash-w8a8-mtp", topology=Topology.STANDALONE, engine="vllm-ascend")
    resolved = resolve_config(env, target, UserInput())
    assert resolved.resolution_notes.get("asset_source") == "v2"
    assert "v2" in str(resolved.resolution_notes.get("matched_model_yaml", ""))


def test_v2_miss_falls_back_to_v1(config_root_real, tmp_path, monkeypatch):
    """v2 未命中（模型不在 v2 资产树）→ 回退 v1（asset_source == 'v1'）。"""
    monkeypatch.setenv("ENGINE_VERSION", "v0.23.0")
    hw = _write_hardware(tmp_path, "Ascend910_64G")
    env = _make_env(config_root_real, hw)
    # v2 资产树只有 DeepSeek-V4-Flash-w8a8-mtp；GLM-5-w8a8 在 v1 存在 → v2 未命中回退 v1。
    target = Target(model_name="GLM-5-w8a8", topology=Topology.STANDALONE, engine="vllm-ascend")
    resolved = resolve_config(env, target, UserInput())
    assert resolved.resolution_notes.get("asset_source") == "v1"


def test_v2_qwen38_2_4t_four_node_worker_recipe(config_root_real, tmp_path, monkeypatch):
    """Qwen3.8-2.4T W8A8 resolves to the supplied four-node v0.30.0rc2 recipe."""
    monkeypatch.setenv("ENGINE_VERSION", "v0.30.0rc2")
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    monkeypatch.setattr("wings_ctl.core.config_resolver._detect_cpu_arch", lambda: "aarch64")
    hw = _write_hardware(tmp_path, "Ascend910C_64G")
    env = _make_env(config_root_real, hw)
    target = Target(
        model_name="Qwen3.8-2.4T-A95B-w8a8",
        topology=Topology.MULTI_NODE,
        engine="vllm-ascend",
    )
    resolved = resolve_config(
        env,
        target,
        UserInput(cli_overrides={"model": "/models/Qwen3.8-2.4T-A95B-w8a8"}),
        placement=ClusterPlacement(
            rank_ip="10.0.0.3",
            node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"],
            master_ip="10.0.0.1",
        ),
    )

    assert resolved.resolution_notes.get("asset_source") == "v2"
    assert resolved.resolution_notes["multi_node_role"] == "worker"
    assert resolved.resolution_notes["multi_node_index"] == "2"
    assert resolved.engine_config_traces["headless"].final_value is True
    assert resolved.engine_config_traces["model"].final_value == "/models/Qwen3.8-2.4T-A95B-w8a8"
    assert resolved.engine_config_traces["tensor_parallel_size"].final_value == 16
    assert resolved.engine_config_traces["data_parallel_size"].final_value == 4
    assert resolved.engine_config_traces["data_parallel_start_rank"].final_value == 2
    assert resolved.engine_config_traces["data_parallel_address"].final_value == "10.0.0.1"
    assert resolved.engine_config_traces["speculative_config"].final_value == {
        "method": "qwen3_5_mtp",
        "num_speculative_tokens": 1,
    }
    assert resolved.engine_config_traces["additional_config"].final_value == {
        "enable_cpu_binding": True,
        "enable_fused_mc2": 1,
    }
    assert resolved.accel.audit["smart_decoding_scheme"] == "qwen3_5_mtp"
    argv = build_argv(resolved.engine_config_traces, engine="vllm-ascend")
    assert argv[:3] == ["vllm", "serve", "/models/Qwen3.8-2.4T-A95B-w8a8"]
    assert argv[argv.index("--speculative-config") + 1] == (
        '{"method":"qwen3_5_mtp","num_speculative_tokens":1}'
    )
    assert argv[argv.index("--additional-config") + 1] == (
        '{"enable_cpu_binding":true,"enable_fused_mc2":1}'
    )
