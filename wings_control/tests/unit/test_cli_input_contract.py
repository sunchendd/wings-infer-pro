from __future__ import annotations

import json
from pathlib import Path

import pytest

from wings_ctl import cli
from wings_ctl.translators.cli_translator import CLITranslator, filter_maas_contract_overrides


def test_named_flags_collected_to_user_cli_raw_dict():
    out = cli._collect_user_cli_overrides(
        host=None,
        port=None,
        model_path="/m",
        model_name="X",
        max_num_seqs=256,
        input_length=4096,
        output_length=4096,
        trust_remote_code=True,
        enable_auto_think_choice=True,
        enable_auto_tool_choice=True,
        gpu_memory_utilization=0.9,
        seed=42,
    )
    assert out["model_path"] == "/m"
    assert out["model_name"] == "X"
    assert out["max_num_seqs"] == 256
    assert out["input_length"] == 4096
    assert out["output_length"] == 4096
    assert out["trust_remote_code"] is True
    assert out["enable_auto_think_choice"] is True
    assert out["enable_auto_tool_choice"] is True
    assert out["gpu_memory_utilization"] == 0.9
    assert out["seed"] == 42


def test_sugar_host_port_model_path_collected(monkeypatch):
    """proxy 迁移:用户 --port 是 proxy 端口 → engine override 取 backend 端口(ENGINE_PORT/17000)。

    G2:`_collect_user_cli_overrides` 现在**只读不写 env**(proxy 端口写 env 见下方 _export_proxy_port 测试)。
    """
    monkeypatch.delenv("ENGINE_PORT", raising=False)
    out = cli._collect_user_cli_overrides(
        host="0.0.0.0",
        port=18000,  # 用户传的是 proxy 端口
        model_path="/weights",
    )
    assert out == {"host": "0.0.0.0", "port": 17000, "model_path": "/weights"}  # engine 监听 backend 17000


def test_export_proxy_port_sets_env(monkeypatch):
    """G2:--port(对外/代理端口)由 _export_proxy_port 显式写入 env PORT(供 proxy 读)。"""
    monkeypatch.delenv("PORT", raising=False)
    cli._export_proxy_port(18000)
    import os

    assert os.environ.get("PORT") == "18000"


def test_export_proxy_port_none_no_write(monkeypatch):
    """G2:--port 未传(None)→ 不写 env(保持原样)。"""
    monkeypatch.delenv("PORT", raising=False)
    cli._export_proxy_port(None)
    import os

    assert os.environ.get("PORT") is None


def test_pd_drops_standard_backend_port_compat_but_keeps_audit():
    """PD 的 backend 由 exact recipe 规划，MaaS --port 只保留 proxy 语义。"""
    overrides, dropped = cli._drop_pd_backend_port_compat(
        {"port": 17000, "max_num_seqs": 16},
        [],
    )

    assert overrides == {"max_num_seqs": 16}
    assert dropped == [
        {
            "key": "port",
            "value": 17000,
            "reason": "PD engine backend port is owned by the exact recipe; --port remains proxy PORT",
        }
    ]


def test_pd_port_compat_drop_is_noop_without_generated_port():
    """未传 --port 时不制造 dropped 记录。"""
    overrides = {"max_num_seqs": 16}
    dropped = [{"key": "input_length", "value": 8, "reason": "unsupported"}]

    assert cli._drop_pd_backend_port_compat(overrides, dropped) == (overrides, dropped)


def test_model_flag_not_part_of_overrides():
    out = cli._collect_user_cli_overrides(host=None, port=None, model_path=None)
    assert "model_name" not in out
    assert "model" not in out
    assert "model_path" not in out


def test_named_flags_translation_to_engine_keys_and_drop():
    raw = cli._collect_user_cli_overrides(
        host="0.0.0.0",
        port=18000,
        model_path="/m",
        model_name="X",
        max_num_seqs=256,
        input_length=4096,
        gpu_memory_utilization=0.9,
        seed=42,
        trust_remote_code=True,
    )
    translated, dropped = CLITranslator.translate_overrides(raw, "vllm")
    assert translated["model"] == "/m"
    assert translated["served_model_name"] == "X"
    assert translated["max_num_seqs"] == 256
    assert translated["trust_remote_code"] is True
    assert translated["host"] == "0.0.0.0"
    assert translated["port"] == 17000  # proxy 迁移:engine 监听 backend 端口(用户 proxy 端口入 env PORT)
    # 评审定:gpu_memory_utilization / seed 现在直通(user_cli 覆盖 recipe)
    assert translated["gpu_memory_utilization"] == 0.9
    assert translated["seed"] == 42
    dropped_keys = {entry["key"] for entry in dropped}
    assert "input_length" in dropped_keys  # 仅 input_length 仍丢弃(vllm 无对应)
    assert "seed" not in dropped_keys and "gpu_memory_utilization" not in dropped_keys


def test_max_num_batched_tokens_passthrough_to_engine_native():
    """验证 --max-num-batched-tokens 收集为 user_cli 并同名直通译为 vllm 原生键(覆盖 recipe)。"""
    raw = cli._collect_user_cli_overrides(
        host=None,
        port=None,
        model_path=None,
        max_num_batched_tokens=4096,
    )
    assert raw["max_num_batched_tokens"] == 4096
    translated, dropped = CLITranslator.translate_overrides(raw, "vllm")
    assert translated["max_num_batched_tokens"] == 4096  # 同名直通,未被丢弃
    assert "max_num_batched_tokens" not in {d["key"] for d in dropped}


def test_parser_accepts_maas_named_flags():
    parser = cli._build_parser()
    args = parser.parse_args(
        [
            "--model-name",
            "X",
            "--max-num-seqs",
            "256",
            "--max-num-batched-tokens",
            "4096",
            "--input-length",
            "4096",
            "--output-length",
            "4096",
            "--trust-remote-code",
            "--enable-auto-think-choice",
            "--enable-auto-tool-choice",
            "--dtype",
            "float16",
            "--gpu-memory-utilization",
            "0.9",
            "--seed",
            "42",
        ]
    )
    assert args.model_name == "X"
    assert args.max_num_seqs == 256
    assert args.max_num_batched_tokens == 4096
    assert args.input_length == 4096
    assert args.output_length == 4096
    assert args.trust_remote_code is True
    assert args.enable_auto_think_choice is True
    assert args.enable_auto_tool_choice is True
    assert args.dtype == "float16"
    assert args.gpu_memory_utilization == 0.9
    assert args.seed == 42


def test_store_true_flags_default_none():
    parser = cli._build_parser()
    args = parser.parse_args(["--model-name", "kimi-k2.5"])
    assert args.trust_remote_code is None
    assert args.enable_auto_think_choice is None
    assert args.enable_auto_tool_choice is None
    assert args.enable_chunked_prefill is None
    assert args.enable_prefix_caching is None
    assert args.enable_expert_parallel is None


def test_store_true_none_not_in_overrides():
    out = cli._collect_user_cli_overrides(
        host=None,
        port=None,
        model_path=None,
        trust_remote_code=None,
        enable_auto_think_choice=None,
        enable_auto_tool_choice=None,
        enable_chunked_prefill=None,
        enable_prefix_caching=None,
        enable_expert_parallel=None,
    )
    assert "trust_remote_code" not in out
    assert "enable_auto_think_choice" not in out
    assert "enable_auto_tool_choice" not in out
    assert "enable_chunked_prefill" not in out
    assert "enable_prefix_caching" not in out
    assert "enable_expert_parallel" not in out


def test_nonexistent_hardware_friendly_error_not_crash(config_root_real, tmp_path, monkeypatch, capsys):
    """验证选不存在的硬件 → 友好报错(SystemExit 2)而非 FileNotFoundError 崩溃(回归:tester 上报)。"""
    hw = tmp_path / "bad_hw.json"
    hw.write_text(
        json.dumps({"hardware_family": "1rtx_pro_5000_72G", "device": "nvidia", "count": 8}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENGINE_VERSION", "v0.18.0")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--engine",
            "vllm",
            "--model-name",
            "Qwen3.5-397B-A17B-NVFP4",
            "--config-root",
            str(config_root_real),
            "--hardware-info",
            str(hw),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )
    with pytest.raises(SystemExit) as exc:  # parser.error → SystemExit(2),不应是 FileNotFoundError
        cli.main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "No configuration assets" in err and "hardware_family" in err


def test_engine_fallback_from_env(monkeypatch):
    monkeypatch.setenv("ENGINE", "vllm-ascend")
    assert cli._resolve_engine(None) == "vllm-ascend"


def test_engine_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("ENGINE", "vllm-ascend")
    assert cli._resolve_engine("vllm") == "vllm"


def test_engine_default_when_no_cli_no_env(monkeypatch):
    monkeypatch.delenv("ENGINE", raising=False)
    assert cli._resolve_engine(None) == "vllm"


def test_hardware_cli_path_used_when_given():
    """--hardware-info 给定时直接用该路径(CLI 是两条途径之一)。"""
    cli_path = Path("/tmp/hw-cli.json")
    assert cli._resolve_hardware_info_path(cli_path) == cli_path


def test_hardware_defaults_to_shared_volume_when_cli_absent():
    """--hardware-info 可选:不传则读固定目录(WINGS_HARDWARE_FILE 入口已删,仅 CLI + 固定目录两途径)。"""
    assert cli._resolve_hardware_info_path(None) == cli.DEFAULT_HARDWARE_INFO_PATH
    assert cli.DEFAULT_HARDWARE_INFO_PATH == Path("/shared-volume/hardware_info.json")


def test_output_dir_cli_value_wins(tmp_path):
    """--output-dir 给定时直接用该值(优先级最高)。"""
    assert cli._resolve_output_dir(tmp_path) == tmp_path


def test_output_dir_defaults_to_shared_volume_when_present(tmp_path, monkeypatch):
    """未传 --output-dir 且共享卷存在 → 三件产物落共享卷(engine 从此读 start_command.sh)。"""
    monkeypatch.setattr(cli, "SHARED_VOLUME_DIR", tmp_path)  # 模拟共享卷已挂载(存在)
    assert cli._resolve_output_dir(None) == tmp_path


def test_output_dir_falls_back_to_cwd_without_shared_volume(monkeypatch):
    """未传 --output-dir 且无共享卷(本地/CI)→ 回退 cwd,行为不变。"""
    monkeypatch.setattr(cli, "SHARED_VOLUME_DIR", Path("/no/such/shared-volume"))
    assert cli._resolve_output_dir(None) == Path(".")


@pytest.mark.parametrize(
    "argv_tokens, collect_kwargs, canonical_key",
    [
        (["--quantization", "fp8"], {"quantization": "fp8"}, "quantization"),
        (["--enable-prefix-caching"], {"enable_prefix_caching": True}, "enable_prefix_caching"),
        (["--enable-expert-parallel"], {"enable_expert_parallel": True}, "enable_expert_parallel"),
    ],
)
def test_known_non_contract_cli_params_are_collected_but_dropped_before_merge(
    argv_tokens, collect_kwargs, canonical_key
):
    """验证:这些 CLI 参数能被 argparse 解析、被 _collect 收成 canonical key,但因不在 MaaS 契约
    白名单,会在进入 user_cli merge 前被 warn-only dropped(reason 固定),不进 translated/applied。

    这是当前 parameter lifecycle / MaaS contract 策略(非契约参数优雅降级),不是解析遗漏或 allowlist 漏项。
    """
    # 1. argparse 能解析(程序认识该参数;dest 与 canonical key 同名)
    parser = cli._build_parser()
    args = parser.parse_args(["--model-name", "X", *argv_tokens])
    assert getattr(args, canonical_key) is not None

    # 2. _collect_user_cli_overrides 收成对应 canonical key(进 raw override dict)
    raw = cli._collect_user_cli_overrides(host=None, port=None, model_path=None, **collect_kwargs)
    assert canonical_key in raw

    # 3. filter_maas_contract_overrides 在 merge 前把它 dropped、不在 allowed
    allowed, dropped = filter_maas_contract_overrides(raw)
    assert canonical_key not in allowed
    dropped_row = next(row for row in dropped if row["key"] == canonical_key)

    # 4. dropped reason 固定为契约拦截原因
    assert dropped_row["reason"] == "maas_status=not_in_maas_contract_allowlist"

    # 5. 经 CLITranslator.translate_overrides 后:不在 translated(不进 argv),且列入 dropped
    translated, translated_dropped = CLITranslator.translate_overrides(raw, "vllm")
    assert canonical_key not in translated
    assert canonical_key in {row["key"] for row in translated_dropped}


def test_env_feature_gates_do_not_leak_into_user_cli_layer(monkeypatch):
    # 覆盖全部四类受控特性开关前缀:ENABLE_* / LMCACHE_* / WINGS_ROUTE_* / PD_ROLE
    monkeypatch.setenv("ENABLE_SPARSE", "true")
    monkeypatch.setenv("LMCACHE_OFFLOAD", "true")
    monkeypatch.setenv("WINGS_ROUTE_ENABLE", "true")
    monkeypatch.setenv("PD_ROLE", "P")
    out = cli._collect_user_cli_overrides(
        host="0.0.0.0",
        port=18000,
        model_path="/m",
        model_name="X",
    )
    assert "ENABLE_SPARSE" not in out
    assert "LMCACHE_OFFLOAD" not in out
    assert "WINGS_ROUTE_ENABLE" not in out
    assert "PD_ROLE" not in out
    assert out["host"] == "0.0.0.0"
    assert out["port"] == 17000  # proxy 迁移:engine override 取 backend 端口
    assert out["model_name"] == "X"
