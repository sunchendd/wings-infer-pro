from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from wings_ctl.core.models import PipelineRequest, Target, UserInput
from wings_ctl.pipeline import run_pipeline


def _run_with_overrides(config_root: Path, hardware_info_path: Path, tmp_path: Path, user_cli_overrides: dict | None):
    os.environ["ENGINE_VERSION"] = "0.18.0"
    try:
        out_dir = tmp_path / ("with_overrides" if user_cli_overrides else "without_overrides")
        out_dir.mkdir(parents=True, exist_ok=True)
        resolved, start_path, repro_path, audit_path = run_pipeline(
            PipelineRequest(
                target=Target(model_name="kimi-k2.5", engine="vllm-ascend"),
                hardware_info_path=hardware_info_path,
                config_root=config_root,
                user_input=UserInput(cli_overrides=user_cli_overrides),
            ),
            output_dir=out_dir,
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        return resolved, start_path, repro_path, audit_path, audit
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def _extract_port_events(audit: dict):
    entry = audit["engine_config"]["port"]
    return entry["final_value"], entry["final_layer"], entry["events"]


def _run_echo_command(script_path: Path) -> str:
    content = script_path.read_text(encoding="utf-8")
    # 替换引擎命令行(后台化后的 "vllm serve ..." 行)为 echo,用于实际执行验证
    lines = content.splitlines()
    engine_idx = next((i for i, ln in enumerate(lines) if ln.startswith("vllm serve ")), -1)
    if engine_idx != -1:
        lines[engine_idx] = "echo " + lines[engine_idx]
    patched = "\n".join(lines) + "\n"
    patched_path = script_path.with_name(f"echo_{script_path.name}")
    patched_path.write_text(patched, encoding="utf-8")
    env = os.environ.copy()
    env.setdefault("LD_PRELOAD", "")
    out = subprocess.run(
        ["bash", str(patched_path)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    cmd_lines = [line for line in out.splitlines() if line.startswith("vllm serve ")]
    assert len(cmd_lines) == 1
    return cmd_lines[0]


def test_engine_param_port_9000_enters_user_cli_layer(config_root_real, tmp_path):
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )

    _, start_path, _, _, audit = _run_with_overrides(
        config_root_real,
        hardware_info_path,
        tmp_path,
        {"port": 9000},
    )

    final_value, final_layer, events = _extract_port_events(audit)
    assert final_value == 9000
    assert isinstance(final_value, int)
    assert final_layer == "user_cli"
    assert len(events) == 3  # builtin_default → model_scenario → user_cli

    assert events[0]["action"] == "set"
    assert events[0]["layer"] == "builtin_default"
    assert events[0]["value"] == 17000

    assert events[1]["action"] == "override"
    assert events[1]["layer"] == "model_scenario"
    assert events[1]["value"] == 8088

    assert events[2]["action"] == "override"
    assert events[2]["layer"] == "user_cli"
    assert events[2]["value"] == 9000
    assert events[2]["source_file"] == "<user_cli>"

    cmd = _run_echo_command(start_path)
    assert "--port 9000" in cmd
    assert "--port 8088" not in cmd
    assert cmd.count("--port ") == 1


def test_sugar_port_9001_path_enters_user_cli_layer(config_root_real, tmp_path):
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )

    _, _, _, _, audit = _run_with_overrides(
        config_root_real,
        hardware_info_path,
        tmp_path,
        {"port": 9001},
    )

    final_value, final_layer, events = _extract_port_events(audit)
    assert final_value == 9001
    assert isinstance(final_value, int)
    assert final_layer == "user_cli"
    assert len(events) == 3  # builtin_default → model_scenario → user_cli
    assert events[-1]["layer"] == "user_cli"
    assert events[-1]["value"] == 9001


def test_no_user_cli_overrides_no_side_effect(config_root_real, tmp_path):
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )

    _, start_path, _, _, audit = _run_with_overrides(
        config_root_real,
        hardware_info_path,
        tmp_path,
        None,
    )

    final_value, final_layer, events = _extract_port_events(audit)
    assert final_value == 8088
    assert isinstance(final_value, int)
    assert final_layer == "model_scenario"
    assert len(events) == 2  # builtin_default(17000) → model_scenario(8088)
    assert events[0]["layer"] == "builtin_default"
    assert events[0]["value"] == 17000
    assert events[1]["layer"] == "model_scenario"
    assert events[1]["value"] == 8088

    cmd = _run_echo_command(start_path)
    assert "--port 8088" in cmd
    assert "--port 9000" not in cmd
    assert "--port 9001" not in cmd
    assert cmd.count("--port ") == 1
