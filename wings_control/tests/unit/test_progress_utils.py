"""启动进度 proxy 的边界测试。"""

from __future__ import annotations

from wings_ctl.common.progress_utils import MAX_STARTUP_PROGRESS, StartupProgressManager


def _progress(progress: int, *, phase_code: str = "ready", status: str = "running") -> dict:
    return {
        "progress": progress,
        "phase_code": phase_code,
        "phase_name": "测试阶段",
        "status": status,
        "key_log": "test",
    }


def test_proxy_caps_log_progress_at_99() -> None:
    """公共 proxy 对外保留 100% 给平台最终状态。"""
    manager = StartupProgressManager("vllm")

    result = manager.update_from_file(_progress(100, status="completed"))

    assert result["progress"] == MAX_STARTUP_PROGRESS == 99
    assert result["status"] == "completed"


def test_proxy_ready_stage_does_not_auto_increment_to_100(monkeypatch) -> None:
    """ready 阶段保持公共 99% 上限，不引入 PD 专用逻辑。"""
    manager = StartupProgressManager("mindie")
    monkeypatch.setattr("wings_ctl.common.progress_utils.random.random", lambda: 0)

    manager.update_from_file(_progress(99))
    result = manager.update_from_file(_progress(99))

    assert manager.stage_definitions["ready"]["max"] == 99
    assert result["progress"] == 99
