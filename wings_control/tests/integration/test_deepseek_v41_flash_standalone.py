"""DeepSeek-V4.1-Flash karmic-kraken 单机配置与 DSpark 回归测试。"""

from __future__ import annotations

import json
import shlex

from wings_ctl import cli


_MODEL_PATH = "/usr/local/serving/models"
_RUNTIME_ENV = {
    "ENGINE_VERSION": "karmic-kraken-20260923",
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
    "--engine-port",
    "17002",
    "--enable-auto-tool-choice",
    "--enable-auto-think-choice",
    "--dry-run",
)
_EXPECTED_SPECULATIVE_CONFIG = {
    "method": "dspark",
    "attention_backend": "B12X",
    "draft_sample_method": "greedy",
    "rejection_sample_method": "standard",
    "num_speculative_tokens": 7,
    "draft_tensor_parallel_size": 8,
    "enable_adaptive_verification": True,
    "adaptive_verification_cost_scale": 1.0,
}
_EXPECTED_JSON_OPTIONS = {
    "--engram-config": {
        "cpu_offload": False,
        "table_memory": "ram",
        "disk_resident_scales": False,
        "projection_tp": False,
    },
    "--compilation-config": {"cudagraph_mode": "FULL_AND_PIECEWISE"},
    "--default-chat-template-kwargs": {
        "thinking": True,
        "reasoning_effort": "high",
    },
    "--override-generation-config": {"temperature": 1.0, "top_p": 0.95},
    "--speculative-config": _EXPECTED_SPECULATIVE_CONFIG,
}
_EXPECTED_OPTION_VALUES = {
    "--served-model-name": "DeepSeek-V4.1-Flash",
    "--tokenizer-mode": "deepseek_v41",
    "--tool-call-parser": "deepseek_v41",
    "--reasoning-parser": "deepseek_v41",
    "--tensor-parallel-size": "8",
    "--kv-cache-dtype": "fp8",
    "--block-size": "256",
    "--swa-block-size": "128",
    "--max-model-len": "133120",
    "--max-num-seqs": "128",
    "--max-num-batched-tokens": "4096",
    "--gpu-memory-utilization": "0.97",
    "--load-format": "instanttensor",
    "--safetensors-load-strategy": "lazy",
    "--attention-backend": "B12X",
    "--moe-backend": "b12x",
    "--linear-backend": "b12x",
    "--max-cudagraph-capture-size": "128",
    "--prefill-compute-share": "0.4",
    "--generation-config": "vllm",
    "--host": "0.0.0.0",
    "--port": "17002",
}
_EXPECTED_FLAGS = (
    "--language-model-only",
    "--async-scheduling",
    "--no-scheduler-reserve-full-isl",
    "--enable-prefix-caching",
    "--enable-chunked-prefill",
    "--enable-auto-tool-choice",
)
_EXPECTED_ENV_LINES = (
    "export INSTANTTENSOR_BACKEND=BUFFERED",
    "export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
    "export VLLM_ENGINE_READY_TIMEOUT_S=3600",
    "export VLLM_USE_BREAKABLE_CUDAGRAPH=0",
    "export VLLM_USE_AOT_COMPILE=1",
    "export VLLM_USE_MEGA_AOT_ARTIFACT=1",
    "export VLLM_USE_STANDALONE_COMPILE=1",
    "export B12X_AUTOTUNE=0",
    "export CUTE_DSL_ARCH=sm_120a",
    "export VLLM_ENABLE_PCIE_ALLREDUCE=1",
    "export VLLM_PCIE_ALLREDUCE_BACKEND=b12x",
    "export VLLM_PCIE_DMA_MIN_BYTES=6MB",
    "export VLLM_PCIE_ONESHOT_ALLREDUCE_MAX_SIZE=96KB",
    "export VLLM_PCIE_ONESHOT_FUSED_ADD_RMS_NORM_MAX_SIZE=96KB",
    "export VLLM_PCIE_TWOSHOT_ALLREDUCE_MAX_SIZE=off",
    "export CUDA_DEVICE_MAX_CONNECTIONS=32",
    "export VLLM_MULTI_STREAM_GEMM_TOKEN_THRESHOLD=1024",
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
    for key in ("ENABLE_SPARSE", "ENABLE_KV_OFFLOAD", "SPECULATIVE_DECODE_MODEL_PATH"):
        monkeypatch.delenv(key, raising=False)
    replacements = {"config_root": config_root_real, "hardware_info": hardware_info_path}
    monkeypatch.setattr("sys.argv", [arg.format(**replacements) for arg in _CLI_ARGS])
    cli.main()
    return capsys.readouterr().out


def _option_value(argv, flag):
    """返回命令行选项紧随的值。"""
    return argv[argv.index(flag) + 1]


def _assert_dry_run_output(output):
    """校验基础参数、功能参数、多值参数和环境变量。"""
    command = next(line for line in output.splitlines() if line.startswith("vllm serve "))
    argv = shlex.split(command)
    assert argv[2] == _MODEL_PATH
    for flag, value in _EXPECTED_OPTION_VALUES.items():
        assert _option_value(argv, flag) == value
    for flag, expected in _EXPECTED_JSON_OPTIONS.items():
        assert json.loads(_option_value(argv, flag)) == expected
    for flag in _EXPECTED_FLAGS:
        assert flag in argv
    capture_index = argv.index("--cudagraph-capture-sizes")
    assert argv[capture_index + 1: capture_index + 9] == [
        "1",
        "2",
        "4",
        "8",
        "16",
        "32",
        "64",
        "128",
    ]
    for line in _EXPECTED_ENV_LINES:
        assert line in output


def test_deepseek_v41_flash_standalone_dry_run(
    config_root_real,
    tmp_path,
    monkeypatch,
    capsys,
):
    """自定义引擎版本应命中精确模型与 DSpark SmartAccel 资产。"""
    hardware_info_path = _write_hardware_info(tmp_path)
    output = _run_dry_run(config_root_real, hardware_info_path, monkeypatch, capsys)
    _assert_dry_run_output(output)
