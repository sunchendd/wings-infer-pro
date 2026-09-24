"""DeepSeek-V4.1-Flash vLLM v0.30.0 H20 单机配置回归测试。"""

from __future__ import annotations

import json
import shlex

from wings_ctl import cli


_MODEL_PATH = "/var/ai-model/DeepSeek-V41-Flash"
_RUNTIME_ENV = {
    "ENGINE_VERSION": "v0.30.0-x86_64",
    "PD_ROLE": "none",
    "ENABLE_SPECULATIVE_DECODE": "true",
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
_EXPECTED_SPECULATIVE_CONFIG = {
    "method": "dspark",
    "num_speculative_tokens": 5,
    "draft_sample_method": "probabilistic",
    "rejection_sample_method": "block",
    "enable_adaptive_verification": False,
}
_EXPECTED_COMPILATION_CONFIG = {
    "mode": 1,
    "cudagraph_mode": "FULL_DECODE_ONLY",
}
_EXPECTED_OPTION_VALUES = {
    "--served-model-name": "DeepSeek-V4.1-Flash",
    "--tokenizer-mode": "deepseek_v41",
    "--tool-call-parser": "deepseek_v41",
    "--reasoning-parser": "deepseek_v41",
    "--tensor-parallel-size": "8",
    "--kv-cache-dtype": "fp8_ds_mla",
    "--block-size": "64",
    "--gpu-memory-utilization": "0.92",
    "--port": "17000",
}
_EXPECTED_FLAGS = (
    "--enable-auto-tool-choice",
    "--enable-expert-parallel",
    "--enable-prefix-caching",
    "--language-model-only",
    "--swa-bounded-replay",
)
_EXPECTED_ENV_LINES = (
    "export VLLM_ENGINE_READY_TIMEOUT_S=3600",
    "export VLLM_USE_RUST_FRONTEND=1",
)


def _write_hardware_info(tmp_path):
    """写入测试所需的 H20 141G 八卡硬件信息。"""
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "h20_141G", "device": "nvidia", "count": 8}),
        encoding="utf-8",
    )
    return hardware_info_path


def _run_dry_run(config_root_real, hardware_info_path, monkeypatch, capsys):
    """设置部署输入并返回 CLI dry-run 标准输出。"""
    for key, value in _RUNTIME_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("SPECULATIVE_DECODE_MODEL_PATH", raising=False)
    replacements = {
        "config_root": config_root_real,
        "hardware_info": hardware_info_path,
    }
    monkeypatch.setattr(
        "sys.argv",
        [arg.format(**replacements) for arg in _CLI_ARGS],
    )
    cli.main()
    return capsys.readouterr().out


def _option_value(argv, flag):
    """返回命令行选项的紧随值，缺失时让测试直接失败。"""
    return argv[argv.index(flag) + 1]


def _assert_json_option(argv, flag, expected):
    """校验 JSON 类型命令参数的解析结果。"""
    assert json.loads(_option_value(argv, flag)) == expected


def _assert_option_values(argv):
    """校验所有带值参数。"""
    for flag, value in _EXPECTED_OPTION_VALUES.items():
        assert _option_value(argv, flag) == value


def _assert_flags(argv):
    """校验新版 vLLM 配置要求的裸开关。"""
    for flag in _EXPECTED_FLAGS:
        assert flag in argv


def _assert_env(output):
    """校验配置环境变量已进入 dry-run。"""
    for line in _EXPECTED_ENV_LINES:
        assert line in output


def _assert_dry_run_output(output):
    """校验基础参数、功能参数和环境变量均进入最终 dry-run。"""
    command = next(line for line in output.splitlines() if line.startswith("vllm serve "))
    argv = shlex.split(command)
    assert argv[2] == _MODEL_PATH
    assert argv.count("--speculative-config") == 1
    _assert_json_option(argv, "--speculative-config", _EXPECTED_SPECULATIVE_CONFIG)
    _assert_json_option(argv, "--compilation-config", _EXPECTED_COMPILATION_CONFIG)
    _assert_option_values(argv)
    _assert_flags(argv)
    _assert_env(output)


def test_deepseek_v41_flash_v030_h20_dry_run(
    config_root_real,
    tmp_path,
    monkeypatch,
    capsys,
):
    """H20 配置应还原用户命令，并从同版本 SmartAccel 资产启用 DSpark。"""
    hardware_info_path = _write_hardware_info(tmp_path)
    output = _run_dry_run(config_root_real, hardware_info_path, monkeypatch, capsys)
    _assert_dry_run_output(output)
