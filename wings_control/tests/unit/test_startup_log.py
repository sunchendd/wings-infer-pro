from __future__ import annotations

import json
import logging
from pathlib import Path

from wings_ctl.core.topology import Topology
from wings_ctl.core.models import PipelineRequest, Target, UserInput
from wings_ctl.pipeline import run_pipeline


def _run_once(
    *,
    config_root_real: Path,
    tmp_path: Path,
    monkeypatch,
    output_name: str,
    engine_version: str,
    log_path: Path,
    user_cli_overrides: dict | None = None,
    user_cli_dropped: list[dict] | None = None,
    device_count: int | None = None,
) -> Path:
    hardware_info_path = tmp_path / f"{output_name}_hardware.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    output_dir = tmp_path / output_name
    monkeypatch.setenv("ENGINE_VERSION", engine_version)
    monkeypatch.setenv("WINGS_START_LOG", str(log_path))

    run_pipeline(
        PipelineRequest(
            target=Target(model_name="DeepSeek-V4-Flash", topology=Topology.STANDALONE, engine="vllm-ascend"),
            hardware_info_path=hardware_info_path,
            config_root=config_root_real,
            user_input=UserInput(cli_overrides=user_cli_overrides, cli_dropped=user_cli_dropped),
            device_count=device_count,
        ),
        output_dir=output_dir,
    )
    return output_dir


def test_startup_log_normal_contains_required_summary(
    config_root_real,
    tmp_path,
    monkeypatch,
):
    log_path = tmp_path / "logs" / "wings_start.log"
    _run_once(
        config_root_real=config_root_real,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        output_name="normal",
        engine_version="0.18.0",
        log_path=log_path,
        user_cli_overrides={"served_model_name": "maas-demo-service", "port": 18000},
        user_cli_dropped=[
            {
                "key": "gpu_memory_utilization",
                "value": 0.55,
                "reason": "maas_status=删掉(不覆盖recipe基线)",
            }
        ],
    )

    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "[STARTUP] ts=" in content
    assert "hardware=ascend-a3" in content
    assert "engine=vllm-ascend" in content
    assert "resolved_config_version=0.18.0" in content
    assert "[STARTUP] artifacts:" in content
    assert f"log={log_path}" in content
    assert "[STARTUP] user_cli_params: applied=2 dropped=1" in content
    assert "[STARTUP] dropped: gpu_memory_utilization reason=maas_status=删掉(不覆盖recipe基线)" in content


def test_startup_log_contains_fallback_warning_when_version_fallback(
    config_root_real,
    tmp_path,
    monkeypatch,
):
    log_path = tmp_path / "logs" / "fallback.log"
    _run_once(
        config_root_real=config_root_real,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        output_name="fallback",
        engine_version="99.99.99",
        log_path=log_path,
    )

    content = log_path.read_text(encoding="utf-8")
    assert "WARNING: ENGINE_VERSION=99.99.99" in content
    assert "回退到最新支持版本 0.18.0" in content


def test_startup_log_downgrades_to_output_dir_when_target_unwritable(
    config_root_real,
    tmp_path,
    monkeypatch,
    caplog,
):
    blocked = tmp_path / "blocked_parent"
    blocked.write_text("not-a-directory", encoding="utf-8")
    unwritable_target = blocked / "wings_start.log"

    with caplog.at_level(logging.WARNING):
        output_dir = _run_once(
            config_root_real=config_root_real,
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            output_name="downgrade",
            engine_version="0.18.0",
            log_path=unwritable_target,
        )

    fallback_path = output_dir / "wings_start.log"
    assert fallback_path.exists()
    # 显式 WINGS_START_LOG(_run_once 设置)写不进 → WARNING + 降级路径可见
    assert any("startup log 写入" in r.message for r in caplog.records)
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert str(fallback_path) in caplog.text


def test_startup_log_appends_multiple_startup_blocks(
    config_root_real,
    tmp_path,
    monkeypatch,
):
    log_path = tmp_path / "append" / "wings_start.log"
    _run_once(
        config_root_real=config_root_real,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        output_name="append_first",
        engine_version="0.18.0",
        log_path=log_path,
    )
    _run_once(
        config_root_real=config_root_real,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        output_name="append_second",
        engine_version="0.18.0",
        log_path=log_path,
    )

    content = log_path.read_text(encoding="utf-8")
    assert content.count("[STARTUP] ===== ts=") == 2
    assert content.count("[STARTUP] artifacts:") == 2


def test_startup_log_default_path_unwritable_is_quiet_no_warning(
    config_root_real,
    tmp_path,
    monkeypatch,
    caplog,
):
    """默认 /var/log/wings 不可写(dev/非 root 常态)→ 安静降级,绝不打 WARNING(免吓到直接跑命令的同事)。

    不显式设 WINGS_START_LOG,走默认路径;无论默认是否可写,都不应出现"startup log 写入失败"的 WARNING。
    """
    monkeypatch.delenv("WINGS_START_LOG", raising=False)  # 用默认 /var/log/wings 路径
    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    hardware_info_path = tmp_path / "hw.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "defpath"
    with caplog.at_level(logging.INFO):
        run_pipeline(
            PipelineRequest(
                target=Target(model_name="DeepSeek-V4-Flash", topology=Topology.STANDALONE, engine="vllm-ascend"),
                hardware_info_path=hardware_info_path,
                config_root=config_root_real,
            ),
            output_dir=output_dir,
        )
    # 关键:默认路径降级不得产生 WARNING(只允许 INFO)
    assert not any(
        r.levelno >= logging.WARNING and "startup log" in r.getMessage()
        for r in caplog.records
    )


def test_startup_log_is_warn_only_never_drop_semantics(
    config_root_real,
    tmp_path,
    monkeypatch,
):
    """红线守护(D1):丢弃项以"记录 + reason"呈现,日志绝不出现 drop_unsupported 语义。"""
    log_path = tmp_path / "warnonly" / "wings_start.log"
    _run_once(
        config_root_real=config_root_real,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        output_name="warnonly",
        engine_version="0.18.0",
        log_path=log_path,
        user_cli_dropped=[
            {
                "key": "seed",
                "value": 42,
                "reason": "maas_status=删掉(不覆盖recipe基线)",
            }
        ],
    )

    content = log_path.read_text(encoding="utf-8")
    # 必须是"记录 + reason"
    assert "[STARTUP] dropped: seed reason=maas_status=删掉(不覆盖recipe基线)" in content
    # 绝不能出现 drop-unsupported 语义(旧 wings-control 的行为,已被 warn-only 取代)
    for forbidden in ("drop_unsupported", "action=drop", "policy=drop"):
        assert forbidden not in content


def test_startup_log_reports_device_count_when_provided(
    config_root_real,
    tmp_path,
    monkeypatch,
):
    """device_count 有值时如实上报,并体现 DP 协调(DP=cnt//TP,strategy_device_count)。"""
    log_path = tmp_path / "devcount" / "wings_start.log"
    _run_once(
        config_root_real=config_root_real,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        output_name="devcount",
        engine_version="0.18.0",
        log_path=log_path,
        device_count=8,  # DeepSeek-V4-Flash TP=4 → DP=2
    )

    content = log_path.read_text(encoding="utf-8")
    assert "device_count=8" in content
    assert "DP=2" in content
    assert "strategy_device_count" in content

