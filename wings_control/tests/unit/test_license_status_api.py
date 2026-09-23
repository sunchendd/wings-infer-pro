"""health 服务 GET /license_status 路由:读共享卷状态文件原样返回,不触发校验。

路由须注册在 catch-all 透传路由之前,否则会被引擎端点白名单拦截(403)。
"""

import json

from fastapi.testclient import TestClient

from wings_ctl.proxy import health_service


def test_license_status_returns_file_payload(tmp_path, monkeypatch):
    """状态文件存在且合法:HTTP 200,载荷与落盘 JSON 完全一致。"""
    status_file = tmp_path / "license_status.json"
    payload = {
        "status": "valid",
        "code": 2000,
        "checked_at": "2026-09-23T00:00:00Z",
        "alarm_interval_seconds": 28800,
    }
    status_file.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(health_service, "LICENSE_STATUS_FILE", status_file)

    with TestClient(health_service.app) as client:
        resp = client.get("/license_status")

    assert resp.status_code == 200
    assert resp.json() == payload


def test_license_status_unavailable_when_file_missing(tmp_path, monkeypatch):
    """状态文件缺失(普通镜像/首轮巡检未落盘):HTTP 503,不触发校验。"""
    monkeypatch.setattr(health_service, "LICENSE_STATUS_FILE", tmp_path / "absent.json")

    with TestClient(health_service.app) as client:
        resp = client.get("/license_status")

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == 503
    assert body["data"] is None
    assert "license status unavailable" in body["msg"]


def test_license_status_unavailable_when_file_corrupt(tmp_path, monkeypatch):
    """状态文件损坏(非法 JSON):HTTP 503,与文件缺失同口径。"""
    status_file = tmp_path / "license_status.json"
    status_file.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(health_service, "LICENSE_STATUS_FILE", status_file)

    with TestClient(health_service.app) as client:
        resp = client.get("/license_status")

    assert resp.status_code == 503
    assert resp.json()["code"] == 503
