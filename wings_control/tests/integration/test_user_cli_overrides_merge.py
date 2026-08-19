from __future__ import annotations

import json
import os
from pathlib import Path

from tests.script_test_utils import run_vllm_command_as_echo
from wings_ctl.core.models import PipelineRequest, Target, UserInput
from wings_ctl.pipeline import run_pipeline


def _run_with_overrides(config_root: Path, hardware_info_path: Path, tmp_path: Path, user_cli_overrides: dict | None):
    os.environ["ENGINE_VERSION"] = "v0.18.0"
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

    cmd = run_vllm_command_as_echo(start_path)
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

    cmd = run_vllm_command_as_echo(start_path)
    assert "--port 8088" in cmd
    assert "--port 9000" not in cmd
    assert "--port 9001" not in cmd
    assert cmd.count("--port ") == 1
