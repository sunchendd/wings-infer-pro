"""`/v1/startup/progress` 接口级契约测试。

重点保护公共 99% 契约:即使 analyzer 在进度文件中写 progress=100 /
status="completed",proxy 也必须对外只返回 progress=99。最终 100%/"运行中"
/失败由 FOA 独立判定,wings-control 不向外部宣告部署完成。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wings_ctl.common import settings
from wings_ctl.common.progress_utils import MAX_STARTUP_PROGRESS
from wings_ctl.proxy.health_service import app


def _mark_completed_line(progress: int = 100) -> str:
    """模拟 analyzer 完成态写入 progress.jsonl 的最后一行。"""
    return json.dumps(
        {
            "progress": progress,
            "phase_code": "ready",
            "phase_name": "等待平台确认",
            "status": "completed",
            "key_log": "Log analyzer reached the ready pattern; service status is owned by FOA",
        }
    )


@pytest.fixture()
def api(monkeypatch, tmp_path: Path):
    progress_file = tmp_path / "progress.jsonl"
    # 指向临时 progress 文件;settings 已按环境变量生成 PROGRESS_FILE。
    monkeypatch.setattr(settings.settings, "PROGRESS_FILE", str(progress_file))

    from fastapi.testclient import TestClient

    # TestClient 上下文会触发 FastAPI startup 事件,初始化 app.state.progress_manager。
    with TestClient(app) as client:
        yield client, progress_file


def test_progress_api_caps_analyzer_100_to_99(api) -> None:
    """analyzer 写 100/completed 后,对外接口恒为 progress=99 且保留 completed 透传。"""
    client, progress_file = api
    progress_file.write_text(_mark_completed_line(100) + "\n", encoding="utf-8")

    resp = client.get("/v1/startup/progress")
    assert resp.status_code == 200
    data = resp.json()["data"]

    # 公共 99% 封顶:analyzer 的 100 不得对外暴露
    assert data["progress"] == MAX_STARTUP_PROGRESS == 99
    # status 是 analyzer 写下的内部完成标识,经 proxy 字段透传;FOA 不消费它,
    # 仅读 progress 数值。断言它如实反映 analyzer 状态即可(无需改成 running)。
    assert data["status"] == "completed"
