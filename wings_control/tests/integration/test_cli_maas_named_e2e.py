from __future__ import annotations

import json
import subprocess

from wings_ctl import cli


def _run_echo_command(script_path):
    content = script_path.read_text(encoding="utf-8")
    patched = content.replace("exec ", "echo ", 1)
    patched_path = script_path.with_name(f"echo_{script_path.name}")
    patched_path.write_text(patched, encoding="utf-8")
    out = subprocess.run(
        ["bash", str(patched_path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    cmd_lines = [line for line in out.splitlines() if line.startswith("vllm serve ")]
    assert len(cmd_lines) == 1
    return cmd_lines[0]


def test_cli_maas_named_params_end_to_end(config_root_real, tmp_path, monkeypatch):
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--config-root",
            str(config_root_real),
            "--hardware-info",
            str(hardware_info_path),
            "--output-dir",
            str(output_dir),
            "--engine",
            "vllm-ascend",
            "--model-name",
            "Qwen3-Next",
            "--model-path",
            "/tmp/models/",
            "--device-count",
            "4",
            "--port",
            "18000",
            "--input-length",
            "4096",
            "--output-length",
            "4096",
            "--gpu-memory-utilization",
            "0.9",
            "--seed",
            "42",
            "--max-num-seqs",
            "256",
            "--trust-remote-code",
        ],
    )

    cli.main()

    start_path = output_dir / "start_command.sh"
    repro_path = output_dir / "repro.sh"
    audit_path = output_dir / "audit.json"
    assert start_path.exists()
    assert repro_path.exists()
    assert audit_path.exists()

    cmd = _run_echo_command(start_path)
    assert "vllm serve /tmp/models/" in cmd
    assert "--served-model-name Qwen3-Next" in cmd
    assert "--port 17000" in cmd   # proxy 迁移:用户 --port 18000 是 proxy 端口,engine 监听 backend 17000
    assert "--max-num-seqs 256" in cmd
    assert "--trust-remote-code" in cmd
    # 评审定:gpu_memory_utilization / seed 现在直通(user_cli 覆盖 recipe)→ 进 argv
    assert "--gpu-memory-utilization 0.9" in cmd
    assert "--seed 42" in cmd
    # input/output-length 仍丢弃(vllm 无对应)
    assert "--input-length" not in cmd
    assert "--output-length" not in cmd

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    for key in ["served_model_name", "model", "port", "max_num_seqs", "trust_remote_code",
                "gpu_memory_utilization", "seed"]:
        entry = audit["engine_config"][key]
        assert entry["final_layer"] == "user_cli"
        assert entry["source_file"] == "<user_cli>"

    dropped_rows = [
        r
        for r in audit.get("user_cli_params", [])
        if r.get("status") == "dropped"
    ]
    dropped_keys = {row.get("key") for row in dropped_rows}
    assert {"input_length", "output_length"}.issubset(dropped_keys)   # 仅这两个仍丢弃
    assert "seed" not in dropped_keys and "gpu_memory_utilization" not in dropped_keys
    assert all("reason" in row for row in dropped_rows)


def test_cli_enable_auto_think_choice_dropped_warn_and_keeps_recipe(config_root_real, tmp_path, monkeypatch, caplog):
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "think_mode_out"

    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--model-name",
            "DeepSeek-V4-Flash",
            "--config-root",
            str(config_root_real),
            "--hardware-info",
            str(hardware_info_path),
            "--output-dir",
            str(output_dir),
            "--engine",
            "vllm-ascend",
            "--enable-auto-think-choice",
        ],
    )
    with caplog.at_level("WARNING"):
        cli.main()

    start_path = output_dir / "start_command.sh"
    audit_path = output_dir / "audit.json"
    cmd = _run_echo_command(start_path)
    assert "--enable-auto-think-choice" not in cmd
    assert "--reasoning-parser deepseek_v4" in cmd
    # 警告文案已更新为"由 FeatureOverlay reasoning gate 接管"(与上方 --reasoning-parser 实际渲染一致)。
    assert "FeatureOverlay" in caplog.text

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    dropped_rows = [
        r
        for r in audit.get("user_cli_params", [])
        if r.get("status") == "dropped"
    ]
    assert any(
        row.get("key") == "enable_auto_think_choice"
        and "FeatureOverlay" in str(row.get("reason"))
        for row in dropped_rows
    )
