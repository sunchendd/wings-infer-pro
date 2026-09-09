"""vllm-ascend recipe 的 source system_setup 命令产物回归。"""

from __future__ import annotations

import json

from wings_ctl import cli
from wings_ctl.core.config_resolver import resolve_config
from wings_ctl.core.models import ResolvedEnv, Target
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.rendering.script_builder import build_scripts


def test_recipe_source_commands_precede_vllm_serve(config_root_real, tmp_path, monkeypatch):
    """真实 v0.21.0rc recipe 的 Ascend 初始化命令写入两份执行脚本。"""
    hardware_file = tmp_path / "hardware_info.json"
    hardware_file.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENGINE_VERSION", "v0.21.0rc1")
    hardware = resolve_hardware(hardware_file)
    engine_version = resolve_engine_version(config_root_real, hardware.hardware_family, engine="vllm-ascend")
    resolved = resolve_config(
        ResolvedEnv(config_root=config_root_real, hardware=hardware, engine_version=engine_version),
        Target(model_name="Qwen3.5-27B", topology=Topology.STANDALONE, engine="vllm-ascend"),
    )

    start_path, repro_path = build_scripts(resolved, tmp_path / "out")
    start_content = start_path.read_text(encoding="utf-8")
    repro_content = repro_path.read_text(encoding="utf-8")

    source_toolkit = "source /usr/local/Ascend/ascend-toolkit/set_env.sh"
    source_atb = "source /usr/local/Ascend/nnal/atb/set_env.sh"
    engine_command = "vllm serve Qwen/Qwen3.5-27B"

    assert start_content.index(source_toolkit) < start_content.index(source_atb) < start_content.index(engine_command)
    assert (
        repro_content.index(source_toolkit)
        < repro_content.index(source_atb)
        < repro_content.index(f"exec {engine_command}")
    )


def test_dry_run_prints_recipe_source_commands(config_root_real, tmp_path, monkeypatch, capsys):
    """dry-run 明确展示将位于 vllm serve 前的 Ascend source 命令。"""
    hardware_file = tmp_path / "hardware_info.json"
    hardware_file.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENGINE_VERSION", "v0.21.0rc1")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--engine",
            "vllm-ascend",
            "--model-name",
            "Qwen3.5-27B",
            "--hardware-info",
            str(hardware_file),
            "--config-root",
            str(config_root_real),
            "--dry-run",
        ],
    )

    cli.main()

    output = capsys.readouterr().out
    source_toolkit = "source /usr/local/Ascend/ascend-toolkit/set_env.sh"
    source_atb = "source /usr/local/Ascend/nnal/atb/set_env.sh"
    engine_command = "vllm serve Qwen/Qwen3.5-27B"

    assert "# System Setup source commands" in output
    assert output.index(source_toolkit) < output.index(source_atb) < output.index(engine_command)
