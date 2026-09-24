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


def test_glm53_flash_dry_run_keeps_manual_feature_args_without_source(
    config_root_real, tmp_path, monkeypatch, capsys
):
    """GLM-5.3-Flash 手工 recipe 的环境变量和 feature argv 保持可复现。"""
    hardware_file = tmp_path / "hardware_info.json"
    hardware_file.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENGINE_VERSION", "glm-5.3-flash-a3")
    monkeypatch.setenv("PD_ROLE", "none")
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--config-root",
            str(config_root_real),
            "--hardware-info",
            str(hardware_file),
            "--engine",
            "vllm-ascend",
            "--model-path",
            "/var/ai-model/GLM-5.3-Flash-w8a8",
            "--device-count",
            "16",
            "--trust-remote-code",
            "--enable-auto-tool-choice",
            "--enable-auto-think-choice",
            "--dry-run",
        ],
    )

    cli.main()

    output = capsys.readouterr().out

    assert "# System Setup source commands" not in output
    assert "export PYTORCH_NPU_ALLOC_CONF=expandable_segments:True" in output
    assert "export HCCL_OP_EXPANSION_MODE=AIV" in output
    assert "export HCCL_BUFFSIZE=400" in output
    assert "--served-model-name glm-5.3-flash-w8a8" in output
    assert "--tool-call-parser glm47 --enable-auto-tool-choice" in output
    assert "--reasoning-parser glm45" in output
    assert '--speculative-config \'{"num_speculative_tokens":3,"method":"deepseek_mtp",' in output


_QWEN38_EXPECTED_OUTPUT = (
    "export VLLM_ENGINE_READY_TIMEOUT_S=3600",
    "--served-model-name Qwen3.8-Flash-Next-w8a8-mtp",
    "--tool-call-parser qwen3_xml",
    "--enable-auto-tool-choice",
    "--reasoning-parser qwen3",
    (
        "--speculative-config "
        '\'{"method":"qwen3_5_mtp","num_speculative_tokens":3,'
        '"enforce_eager":true}\''
    ),
    (
        "--compilation-config "
        '\'{"cudagraph_capture_sizes":[4,8,12,16,20,24,28,32],'
        '"cudagraph_mode":"FULL_DECODE_ONLY"}\''
    ),
    (
        "--additional-config "
        '\'{"enable_cpu_binding":true,'
        '"ascend_compilation_config":{"fuse_norm_quant":false}}\''
    ),
)


def _run_qwen38_flash_next_dry_run(config_root_real, hardware_file, monkeypatch):
    """配置 Qwen3.8 Flash Next 测试环境并执行 dry-run。"""
    monkeypatch.setenv("ENGINE_VERSION", "qwen3.8-next")
    monkeypatch.setenv("PD_ROLE", "none")
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--config-root",
            str(config_root_real),
            "--hardware-info",
            str(hardware_file),
            "--engine",
            "vllm-ascend",
            "--model-name",
            "Qwen3.8-Flash-Next-w8a8-mtp",
            "--model-path",
            "/models",
            "--device-count",
            "8",
            "--trust-remote-code",
            "--enable-auto-tool-choice",
            "--enable-auto-think-choice",
            "--dry-run",
        ],
    )
    cli.main()


def test_qwen38_flash_next_910b3_dry_run_keeps_manual_command(
    config_root_real, tmp_path, monkeypatch, capsys
):
    """Qwen3.8 Flash Next 的 910B3 手工 recipe 保留环境变量、嵌套配置和 feature 参数。"""
    hardware_file = tmp_path / "hardware_info.json"
    hardware_file.write_text(
        json.dumps({"hardware_family": "Ascend910B_64G", "device": "ascend", "count": 8}),
        encoding="utf-8",
    )
    _run_qwen38_flash_next_dry_run(config_root_real, hardware_file, monkeypatch)

    output = capsys.readouterr().out
    for expected in _QWEN38_EXPECTED_OUTPUT:
        assert expected in output
