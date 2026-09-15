"""DeepSeek-V4.1-Flash standalone 配置与 SmartAccel 稀疏方案回归测试。"""

from __future__ import annotations

import json

from wings_ctl import cli


_MODEL_PATH = "/var/aispace/model/ai-storage/ai-prod/platform/DeepSeek-V4.1-Flash"
_RUNTIME_ENV = {
    "ENGINE_VERSION": "deepseekv41-flash-0909",
    "PD_ROLE": "none",
    "ENABLE_SPARSE": "true",
    "SPARSE_LEVEL": "accuracy_first",
}
_CLI_ARGS = (
    "wings-ctl",
    "--config-root",
    "{config_root}",
    "--hardware-info",
    "{hardware_info}",
    "--engine",
    "vllm",
    "--model-name",
    "DeepSeek-V4.1-Flash",
    "--model-path",
    _MODEL_PATH,
    "--device-count",
    "8",
    "--port",
    "17000",
    "--enable-auto-tool-choice",
    "--enable-auto-think-choice",
    "--dry-run",
)
_EXPECTED_COMMAND_PARTS = (
    "--attention-backend FLASHINFER_MLA_SPARSE_DSV41",
    "--kv-cache-dtype fp8",
    "--block-size 128",
    "--hf-overrides '{\"index_topk_freq\":4}'",
    "--no-enable-flashinfer-autotune",
    "--gpu-memory-utilization 0.95",
    "--tensor-parallel-size 8",
    "--tokenizer-mode deepseek_v41",
    "--tool-call-parser deepseek_v41",
    "--enable-auto-tool-choice",
    "--reasoning-parser deepseek_v41",
    "--language-model-only",
    "--port 17000",
    "--served-model-name DeepSeek-V4.1-Flash",
)
_EXPECTED_ENV_LINES = (
    "export VLLM_ENGINE_READY_TIMEOUT_S=3600",
    "export NCCL_P2P_LEVEL=SYS",
    "export NCCL_SHM_DISABLE=1",
)


def _write_hardware_info(tmp_path):
    """写入本用例所需的固定 RTX Pro 5000 硬件信息。"""
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "rtx_pro_5000_72G", "device": "nvidia", "count": 8}),
        encoding="utf-8",
    )
    return hardware_info_path


def _run_dry_run(config_root_real, hardware_info_path, monkeypatch, capsys):
    """配置隔离环境并返回 CLI dry-run 标准输出。"""
    for key, value in _RUNTIME_ENV.items():
        monkeypatch.setenv(key, value)
    for key in ("ENABLE_SPECULATIVE_DECODE", "ENABLE_KV_OFFLOAD"):
        monkeypatch.delenv(key, raising=False)
    replacements = {"config_root": config_root_real, "hardware_info": hardware_info_path}
    monkeypatch.setattr("sys.argv", [arg.format(**replacements) for arg in _CLI_ARGS])
    cli.main()
    return capsys.readouterr().out


def _assert_dry_run_output(output):
    """校验模型参数、功能参数和环境变量均进入 dry-run。"""
    command = next(line for line in output.splitlines() if line.startswith("vllm serve "))
    assert command.startswith(f"vllm serve {_MODEL_PATH} ")
    for part in _EXPECTED_COMMAND_PARTS:
        assert part in command
    for line in _EXPECTED_ENV_LINES:
        assert line in output


def test_deepseek_v41_flash_standalone_dry_run(config_root_real, tmp_path, monkeypatch, capsys):
    """自定义引擎版本应命中精确模型与 SmartAccel 资产并还原启动参数。"""
    hardware_info_path = _write_hardware_info(tmp_path)
    output = _run_dry_run(config_root_real, hardware_info_path, monkeypatch, capsys)
    _assert_dry_run_output(output)
