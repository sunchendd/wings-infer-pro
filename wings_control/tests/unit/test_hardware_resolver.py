"""HardwareResolver 负路径单测:json 非对象 / 缺 hardware_family / 正常解析。"""

from __future__ import annotations

import json

import pytest

from wings_ctl.hardware.resolver import resolve_hardware


def test_resolve_hardware_ok(tmp_path):
    """正常:含 hardware_family → HardwareContext 字段正确(device 带默认;count 等冗余字段进 raw)。"""
    p = tmp_path / "hw.json"
    p.write_text(json.dumps({"hardware_family": "gb200", "device": "nvidia", "count": 8}))
    hw = resolve_hardware(p)
    assert hw.hardware_family == "gb200" and hw.device == "nvidia"
    # count 已不是 HardwareContext 字段(准废),仅作原始 JSON 落 raw 携带审计,不参与逻辑。
    assert hw.raw["count"] == 8


def test_resolve_hardware_non_object_raises(tmp_path):
    """json 顶层不是对象(是数组)→ ValueError(must be a JSON object)。"""
    p = tmp_path / "hw.json"
    p.write_text(json.dumps([1, 2, 3]))
    with pytest.raises(ValueError, match="JSON object"):
        resolve_hardware(p)


def test_resolve_hardware_missing_family_raises(tmp_path):
    """缺 hardware_family → ValueError(missing required field)。"""
    p = tmp_path / "hw.json"
    p.write_text(json.dumps({"device": "nvidia", "count": 8}))
    with pytest.raises(ValueError, match="hardware_family"):
        resolve_hardware(p)
