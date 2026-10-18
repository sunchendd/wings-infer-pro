"""Generate rc2 deployment artifacts through the real resolver without running them."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path

import pytest

from wings_ctl.audit.emitter import emit_audit
from wings_ctl.common.settings import settings
from wings_ctl.core.config_resolver import resolve_config
from wings_ctl.core.models import ClusterPlacement, ResolvedEnv, Target, Topology, UserInput
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.rendering.script_builder import build_scripts


@dataclass(frozen=True)
class DeliveryCase:
    model: str
    speculative_tokens: int
    optional_acceleration_enabled: bool
    kv_offload_enabled: bool
    parsers_enabled: bool


CASES = [
    DeliveryCase("DeepSeek-V4-Flash-0731-w8a8", 7, True, True, True),
    DeliveryCase("DeepSeek-V4-Flash-Vision-Exp-w8a8-QuaRot", 6, True, True, True),
    DeliveryCase("DeepSeek-V4-Flash-Vision-Exp-w8a8-QuaRot", 6, False, False, False),
    DeliveryCase("DeepSeek-V4-Flash-0731-w8a8", 7, True, False, True),
    DeliveryCase("DeepSeek-V4-Flash-0731-w8a8", 7, False, False, False),
]


def find_line_index(lines, *, starts_with=None, contains=None, ends_with=None):
    for index, line in enumerate(lines):
        candidate = line.strip()
        if starts_with is not None and not candidate.startswith(starts_with):
            continue
        if contains is not None and contains not in candidate:
            continue
        if ends_with is not None and not candidate.endswith(ends_with):
            continue
        return index
    raise AssertionError(f"Expected generated script line was not found: {starts_with=}, {contains=}, {ends_with=}")


@pytest.mark.parametrize("case", CASES)
def test_rc2_resolve_and_generated_delivery(config_root_real, tmp_path, monkeypatch, case):
    """覆盖现有加速安装门控、文件交付、parser 及引擎前执行顺序。"""
    for key in (
        "RANK_IP", "MASTER_IP", "NODE_IPS", "PD_ROLE", "DISTRIBUTED", "IS_MOONCAKE_MASTER",
        "SPECULATIVE_DECODE_MODEL_PATH", "ENABLE_DISTRIBUTED_KV_OFFLOAD", "ENABLE_KV_DISK_OFFLOAD",
        "ENABLE_KV_QAT",
    ):
        monkeypatch.delenv(key, raising=False)
    shared = tmp_path / "shared-volume"
    artifact = tmp_path / "accel-volume"
    shared.mkdir()
    artifact.mkdir()
    # Delivery fixture; the generated installer and engine commands are never executed.
    (artifact / "install.py").write_text("raise AssertionError('must not execute')\n", encoding="utf-8")
    env = {
        "ENGINE": "vllm-ascend", "ENGINE_VERSION": "v0.30.0rc2",
        "ENABLE_SPECULATIVE_DECODE": str(case.optional_acceleration_enabled).lower(),
        "ENABLE_SPARSE": str(case.optional_acceleration_enabled).lower(), "SPARSE_LEVEL": "accuracy_first",
        "ENABLE_KV_OFFLOAD": str(case.kv_offload_enabled).lower(),
        "ENABLE_KV_MEM_OFFLOAD": str(case.kv_offload_enabled).lower(),
        "KV_MEM_OFFLOAD_SIZE": "128", "AVAILABLE_POD_MEM_SIZE": str(900 * 1024),
        "SHARED_VOLUME_PATH": shared.as_posix(), "ACCEL_VOLUME_PATH": artifact.as_posix(),
        "NIC_NAME": "lo", "IFACE_NAME": "lo",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("wings_ctl.core.config_resolver._detect_cpu_arch", lambda: "aarch64")
    monkeypatch.setattr("wings_ctl.strategy.post_merge.get_interface_for_ip", lambda _ip: ("lo", True))
    for key, value in {
        "SHARED_VOLUME_PATH": shared.as_posix(),
        "ADVANCED_FEATURES_FILE": (shared / "advanced_features.json").as_posix(),
        "PROGRESS_FILE": (shared / "progress.jsonl").as_posix(),
        "ENGINE_LOG_DIR": (tmp_path / "logs").as_posix(),
        "ENGINE_LOG_FILE": (tmp_path / "logs/engine.log").as_posix(),
    }.items():
        monkeypatch.setattr(settings, key, value)
    hardware_path = tmp_path / "hardware_info.json"
    hardware_path.write_text(json.dumps({
        "hardware_family": "Ascend910C_64G", "device": "ascend", "count": 16,
    }), encoding="utf-8")
    hardware = resolve_hardware(hardware_path)
    engine_version = resolve_engine_version(config_root_real, hardware.hardware_family, engine="vllm-ascend")
    resolved = resolve_config(
        ResolvedEnv(config_root=config_root_real, hardware=hardware, engine_version=engine_version),
        Target(model_name=case.model, topology=Topology.STANDALONE, engine="vllm-ascend"),
        UserInput(cli_overrides={"model": "/models/prepared-weights"}, feature_switches={
            "enable_auto_tool_choice": case.parsers_enabled,
            "enable_auto_think_choice": case.parsers_enabled,
        }),
        device_count=16,
        placement=ClusterPlacement(rank_ip="127.0.0.1"),
    )
    assert resolved.resolution_notes["asset_source"] == "v2"
    config = {name: value.final_value for name, value in resolved.engine_config_traces.items()}
    assert config["tensor_parallel_size"] == config["data_parallel_size"] == 4
    if case.optional_acceleration_enabled:
        assert config["speculative_config"] == {
            "method": "dspark", "num_speculative_tokens": case.speculative_tokens, "enforce_eager": True,
        }
        assert config["hf_overrides"] == {"use_index_cache": True, "index_topk_freq": 4}
    else:
        assert "speculative_config" not in config and "hf_overrides" not in config
    assert (config.get("reasoning_parser") == "deepseek_v4") is case.parsers_enabled
    assert (config.get("tool_call_parser") == "deepseek_v4") is case.parsers_enabled
    assert bool(config.get("enable_auto_tool_choice")) is case.parsers_enabled

    vision = "Vision" in case.model
    assert resolved.accel.packages == []
    assert resolved.accel.enabled is (case.optional_acceleration_enabled or case.kv_offload_enabled)
    if case.kv_offload_enabled:
        transfer = config["kv_transfer_config"]
        assert transfer["kv_connector"] == "AscendStoreConnector"
        assert transfer["kv_connector_extra_config"]["backend"] == "memcache"
        assert transfer["kv_load_failure_policy"] == "fail"
        assert len(resolved.accel.generated_files) == 4
    else:
        assert "kv_transfer_config" not in config
        assert not resolved.accel.generated_files

    output = tmp_path / "scripts"
    start, repro = build_scripts(resolved, output)
    audit = emit_audit(resolved, output)
    assert start.is_file() and repro.is_file() and audit.is_file()
    assert json.loads(audit.read_text(encoding="utf-8"))["resolution_notes"]["asset_source"] == "v2"
    lines = start.read_text(encoding="utf-8").splitlines()
    install_lines = [line for line in lines if line.startswith("python3 ") and " --config " in line]
    install_index = None
    if case.optional_acceleration_enabled or case.kv_offload_enabled:
        assert len(install_lines) == 1
        install_argv = shlex.split(install_lines[0])
        assert install_argv[1] == "/accel-volume/install.py"
        assert json.loads(install_argv[install_argv.index("--config") + 1]) == {
            "engine": {"name": "vllm-ascend", "version": "v0.30.0rc2"}, "packages": [],
        }
        install_index = lines.index(install_lines[0])
    else:
        # 原 Control 即使能看到安装工件，全关且无加速产出时也不触发安装。
        assert not install_lines
    prepare_name = "vision-memcache-prepare.sh" if vision else "flash0731-memcache-prepare.sh"
    prepare = find_line_index(lines, starts_with="source ", contains=prepare_name)
    assert lines[prepare - 1].startswith("if [ -f ")
    engine = find_line_index(lines, starts_with="vllm serve ")
    if case.kv_offload_enabled:
        daemon = find_line_index(lines, starts_with="bash ", contains="start_kv_serve.sh", ends_with="&")
        assert install_index is not None and install_index < daemon < prepare < engine
    else:
        assert not any(line.strip().startswith("bash ") and "start_kv_serve.sh" in line for line in lines)
        assert prepare < engine
        if install_index is not None:
            assert install_index < prepare
    for generated in resolved.accel.generated_files:
        path = Path(generated.path)
        assert path.is_file() and path.resolve().is_relative_to(shared.resolve())
        assert generated.source_file == resolved.resolution_notes["matched_model_yaml"]
        assert ".kv_offload[0].files[" in generated.source_path
        if path.name.endswith("local.conf"):
            assert "dram.size = 8GB" in path.read_text(encoding="utf-8")
