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
from wings_ctl.rendering.script_builder import build_scripts
from wings_ctl.validators.engine_param_validator import validate_engine_params


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


def _resolve_v2_qwen3_8_27b_910c(config_root: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ENGINE_VERSION", "v0.30.0rc2")
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    monkeypatch.setenv("RANK_IP", "7.6.28.253")
    monkeypatch.setattr("wings_ctl.core.config_resolver._detect_cpu_arch", lambda: "aarch64")
    monkeypatch.setattr(
        "wings_ctl.strategy.post_merge.get_interface_for_ip",
        lambda _ip: ("bond0", True),
    )
    hw = _write_hardware(tmp_path, "Ascend910C_64G")
    env = _make_env(config_root, hw)
    target = Target(
        model_name="Qwen3.8-27B-w8a8",
        topology=Topology.STANDALONE,
        engine="vllm-ascend",
    )

    return resolve_config(
        env,
        target,
        UserInput(
            cli_overrides={"model": "/var/ai-model/zhanghui/AIperf/Qwen3.8-27B-w8a8"},
            feature_switches={
                "enable_auto_tool_choice": True,
                "enable_auto_think_choice": True,
            }
        ),
        device_count=2,
    )


def _assert_v2_qwen3_8_27b_910c_resolution(resolved, config_root: Path):
    assert resolved.resolution_notes.get("asset_source") == "v2"
    assert resolved.engine_config_traces["model"].final_value == "/var/ai-model/zhanghui/AIperf/Qwen3.8-27B-w8a8"
    assert resolved.engine_config_traces["data_parallel_size"].final_value == 1
    assert resolved.engine_config_traces["tensor_parallel_size"].final_value == 2
    assert resolved.engine_config_traces["speculative_config"].final_value == {
        "method": "qwen3_5_mtp",
        "num_speculative_tokens": 3,
        "enforce_eager": True,
    }
    assert resolved.engine_config_traces["mamba_cache_mode"].final_value == "align"
    assert resolved.accel.audit["smart_decoding_scheme"] == "qwen3_5_mtp"
    assert resolved.env_traces["GLOO_SOCKET_IFNAME"].final_value == "bond0"
    assert resolved.env_traces["TP_SOCKET_IFNAME"].final_value == "bond0"
    assert "ASCEND_RT_VISIBLE_DEVICES" not in resolved.env_traces
    validate_engine_params(resolved, config_root)
    assert resolved.param_validation is not None
    assert resolved.param_validation.unsupported == []


def _assert_v2_qwen3_8_27b_910c_artifacts(resolved, tmp_path: Path):
    argv = build_argv(resolved.engine_config_traces, engine="vllm-ascend")
    assert argv[:3] == ["vllm", "serve", "/var/ai-model/zhanghui/AIperf/Qwen3.8-27B-w8a8"]
    assert argv[argv.index("--speculative-config") + 1] == (
        '{"method":"qwen3_5_mtp","num_speculative_tokens":3,"enforce_eager":true}'
    )
    assert argv[argv.index("--mamba-cache-mode") + 1] == "align"
    assert argv[argv.index("--served-model-name") + 1] == "qwen3.8"
    assert argv[argv.index("--tool-call-parser") + 1] == "qwen3_xml"
    assert argv[argv.index("--reasoning-parser") + 1] == "qwen3"

    start_path, repro_path = build_scripts(resolved, tmp_path / "out")
    for script in (start_path.read_text(encoding="utf-8"), repro_path.read_text(encoding="utf-8")):
        assert script.index("source /usr/local/Ascend/ascend-toolkit/set_env.sh") < script.index(
            "source /usr/local/Ascend/nnal/atb/set_env.sh"
        ) < script.rindex("vllm serve")


def test_v2_qwen3_8_27b_910c_standalone_recipe(config_root_real, tmp_path, monkeypatch):
    """Qwen3.8-27B 910C standalone resolves page features and MTP through v2."""
    resolved = _resolve_v2_qwen3_8_27b_910c(config_root_real, tmp_path, monkeypatch)
    _assert_v2_qwen3_8_27b_910c_resolution(resolved, config_root_real)
    _assert_v2_qwen3_8_27b_910c_artifacts(resolved, tmp_path)


def test_v2_qwen3_8_27b_910c_feature_switches_default_off(config_root_real, tmp_path, monkeypatch):
    """Qwen3.8-27B optional features stay absent until the page enables them."""
    monkeypatch.setenv("ENGINE_VERSION", "v0.30.0rc2")
    monkeypatch.delenv("ENABLE_SPECULATIVE_DECODE", raising=False)
    monkeypatch.setattr("wings_ctl.core.config_resolver._detect_cpu_arch", lambda: "aarch64")
    hw = _write_hardware(tmp_path, "Ascend910C_64G")
    env = _make_env(config_root_real, hw)
    resolved = resolve_config(
        env,
        Target(
            model_name="Qwen3.8-27B-w8a8",
            topology=Topology.STANDALONE,
            engine="vllm-ascend",
        ),
        UserInput(cli_overrides={"model": "/model"}),
        device_count=2,
    )

    assert "tool_call_parser" not in resolved.engine_config_traces
    assert "reasoning_parser" not in resolved.engine_config_traces
    assert "speculative_config" not in resolved.engine_config_traces
    assert resolved.accel.audit.get("smart_decoding_scheme") is None


def test_v2_deepseek_v41_flash_910c_standalone_recipe(config_root_real, tmp_path, monkeypatch):
    """DeepSeek V4.1 Flash 910C standalone retains its v0.30.0rc2 DSpark recipe."""
    monkeypatch.setenv("ENGINE_VERSION", "v0.30.0rc2")
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    monkeypatch.setattr("wings_ctl.core.config_resolver._detect_cpu_arch", lambda: "aarch64")
    hw = _write_hardware(tmp_path, "Ascend910C_64G")
    env = _make_env(config_root_real, hw)
    resolved = resolve_config(
        env,
        Target(
            model_name="DeepSeek-V4.1-Flash-w8a8",
            topology=Topology.STANDALONE,
            engine="vllm-ascend",
        ),
        UserInput(
            feature_switches={
                "enable_auto_tool_choice": True,
                "enable_auto_think_choice": True,
            }
        ),
        device_count=16,
    )

    assert resolved.resolution_notes.get("asset_source") == "v2"
    assert resolved.engine_config_traces["speculative_config"].final_value == {
        "method": "dspark",
        "num_speculative_tokens": 5,
        "enforce_eager": True,
    }
    assert resolved.engine_config_traces["engram_config"].final_value == {
        "cpu_offload": True,
        "dp_shared_memory": True,
    }
    assert resolved.accel.audit["smart_decoding_scheme"] == "dspark"
    validate_engine_params(resolved, config_root_real)
    assert resolved.param_validation is not None
    assert resolved.param_validation.unsupported == []


def test_v1_deepseek_v4_pro_v030rc2_multi_node_recipe(config_root_real, tmp_path, monkeypatch):
    """DeepSeek V4 Pro resolves its v0.30.0rc2 multi-node recipe through v1."""
    monkeypatch.setenv("ENGINE_VERSION", "v0.30.0rc2")
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    monkeypatch.setattr("wings_ctl.core.config_resolver._detect_cpu_arch", lambda: "aarch64")
    hw = _write_hardware(tmp_path, "Ascend910C_64G")
    env = _make_env(config_root_real, hw)
    resolved = resolve_config(
        env,
        Target(
            model_name="DeepSeek-V4-Pro-0813-w4a8",
            topology=Topology.MULTI_NODE,
            engine="vllm-ascend",
        ),
        UserInput(cli_overrides={"model": "/models/DeepSeek-V4-Pro-0813-w4a8"}),
        device_count=16,
        placement=ClusterPlacement(
            rank_ip="10.0.0.1",
            node_ips=["10.0.0.1", "10.0.0.2"],
            master_ip="10.0.0.1",
        ),
    )

    assert resolved.resolution_notes.get("asset_source") == "v1"
    assert resolved.resolution_notes["multi_node_role"] == "head"
    assert resolved.engine_config_traces["model"].final_value == "/models/DeepSeek-V4-Pro-0813-w4a8"
    assert resolved.engine_config_traces["data_parallel_size"].final_value == 2
    assert resolved.engine_config_traces["tensor_parallel_size"].final_value == 16
    assert resolved.engine_config_traces["speculative_config"].final_value == {
        "num_speculative_tokens": 5,
        "method": "dspark",
        "enforce_eager": True,
    }
    assert resolved.engine_config_traces["additional_config"].final_value["mc2_comm_alg"] == "hierarchy"
    validate_engine_params(resolved, config_root_real)
    assert resolved.param_validation is not None
    assert {item["param"] for item in resolved.param_validation.unsupported} == {
        "attention_config.indexer_kv_dtype",
        "no_async_scheduling",
        "prefix_cache_retention_interval",
    }


def test_v2_glm53_flash_910c_feature_and_accel_linkage(config_root_real, tmp_path, monkeypatch):
    """GLM-5.3-Flash v2 enables MTP and MemCache only through their switches."""
    monkeypatch.setenv("ENGINE_VERSION", "v0.30.0rc2")
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    monkeypatch.setenv("ENABLE_KV_OFFLOAD", "true")
    monkeypatch.setenv("KV_MEM_OFFLOAD_SIZE", "128")
    monkeypatch.setattr("wings_ctl.core.config_resolver._detect_cpu_arch", lambda: "aarch64")
    hw = _write_hardware(tmp_path, "Ascend910C_64G")
    env = _make_env(config_root_real, hw)
    resolved = resolve_config(
        env,
        Target(
            model_name="GLM-5.3-Flash-w8a8",
            topology=Topology.STANDALONE,
            engine="vllm-ascend",
        ),
        UserInput(),
        device_count=16,
    )

    assert resolved.resolution_notes.get("asset_source") == "v2"
    assert "tool_call_parser" not in resolved.engine_config_traces
    assert "reasoning_parser" not in resolved.engine_config_traces
    assert resolved.engine_config_traces["speculative_config"].final_value == {
        "num_speculative_tokens": 5,
        "method": "deepseek_mtp",
        "enforce_eager": True,
    }
    assert resolved.engine_config_traces["kv_transfer_config"].final_value["kv_connector"] == "AscendStoreConnector"
    assert resolved.accel.audit["smart_decoding_scheme"] == "deepseek_mtp"
    assert resolved.accel.audit["smart_kv_cache_scheme"] == "cpu"
    validate_engine_params(resolved, config_root_real)
    assert resolved.param_validation is not None
    assert resolved.param_validation.unsupported == []


def test_v2_glm53_flash_910c_function_and_reasoning_features(config_root_real, tmp_path, monkeypatch):
    """GLM-5.3-Flash uses its v2 GLM parsers when the page enables both features."""
    monkeypatch.setenv("ENGINE_VERSION", "v0.30.0rc2")
    monkeypatch.setattr("wings_ctl.core.config_resolver._detect_cpu_arch", lambda: "aarch64")
    hw = _write_hardware(tmp_path, "Ascend910C_64G")
    env = _make_env(config_root_real, hw)
    resolved = resolve_config(
        env,
        Target(
            model_name="GLM-5.3-Flash-w8a8",
            topology=Topology.STANDALONE,
            engine="vllm-ascend",
        ),
        UserInput(feature_switches={"enable_auto_tool_choice": True, "enable_auto_think_choice": True}),
        device_count=16,
    )

    assert resolved.resolution_notes.get("asset_source") == "v2"
    assert resolved.engine_config_traces["tool_call_parser"].final_value == "glm47"
    assert resolved.engine_config_traces["reasoning_parser"].final_value == "glm45"


def test_v1_glm53_w8a8c8_v030rc2_multi_node_recipe(config_root_real, tmp_path, monkeypatch):
    """GLM-5.3 W8A8C8 resolves its v1 multi-node MTP3 configuration."""
    monkeypatch.setenv("ENGINE_VERSION", "v0.30.0rc2")
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    monkeypatch.setattr("wings_ctl.core.config_resolver._detect_cpu_arch", lambda: "aarch64")
    hw = _write_hardware(tmp_path, "Ascend910C_64G")
    env = _make_env(config_root_real, hw)
    resolved = resolve_config(
        env,
        Target(
            model_name="GLM-5.3-w8a8c8",
            topology=Topology.MULTI_NODE,
            engine="vllm-ascend",
        ),
        UserInput(feature_switches={"enable_auto_tool_choice": True, "enable_auto_think_choice": True}),
        device_count=16,
        placement=ClusterPlacement(
            rank_ip="10.0.0.1",
            node_ips=["10.0.0.1", "10.0.0.2"],
            master_ip="10.0.0.1",
        ),
    )

    assert resolved.resolution_notes.get("asset_source") == "v1"
    assert resolved.engine_config_traces["speculative_config"].final_value == {
        "num_speculative_tokens": 3,
        "method": "deepseek_mtp",
        "enforce_eager": True,
    }
    assert resolved.engine_config_traces["tool_call_parser"].final_value == "glm47"
    assert resolved.engine_config_traces["reasoning_parser"].final_value == "glm47"
