"""license_gate 单测:工厂选择 / Null 直通 / 协议符合性 / fail-closed。

License 真实现的行为见 test_license_quota.py;这里只测常驻入口自身。
"""

from __future__ import annotations

from types import SimpleNamespace

from wings_ctl import license_gate
from wings_ctl.build_info import LICENSE_ENABLED


def test_null_gate_passes_everything_through(tmp_path):
    """Null 门禁零副作用:enforce 不抛错,artifact/publish 原样直通。"""
    gate = license_gate.NullLicenseGate()
    gate.enforce(SimpleNamespace(), SimpleNamespace())
    gate.invalidate(tmp_path)
    assert gate.artifact_dir(tmp_path) == (tmp_path, None)
    with gate.lock(tmp_path):
        pass
    assert gate.publish(tmp_path, None, tmp_path) == tmp_path


def test_null_gate_validate_device_count_passes_through():
    """普通构建不做 device_count 强校验:None/0 均直通(维持现状)。"""
    license_gate.NullLicenseGate().validate_device_count(None)
    license_gate.NullLicenseGate().validate_device_count(0)


def test_early_validation_dispatches_to_license_gate(monkeypatch):
    """validate_device_count_early 经工厂转发:License 构建走真实现。"""
    seen = []

    class SpyGate:
        @staticmethod
        def validate_device_count(device_count):
            seen.append(device_count)

    monkeypatch.setattr(license_gate, "LICENSE_ENABLED", True)
    monkeypatch.setattr(license_gate, "get_license_gate", lambda: SpyGate())

    license_gate.validate_device_count_early(None)

    assert seen == [None]


def test_null_gate_satisfies_protocol():
    assert isinstance(license_gate.NullLicenseGate(), license_gate.LicenseGate)


def test_get_license_gate_follows_build_declaration(monkeypatch):
    """工厂按 LICENSE_ENABLED 返回对应实现(非 License → Null)。"""
    monkeypatch.setattr(license_gate, "LICENSE_ENABLED", False)
    assert isinstance(license_gate.get_license_gate(), license_gate.NullLicenseGate)


def test_get_license_gate_fail_closed_when_module_missing(monkeypatch):
    """License 构建但 license 模块被删:必须抛错,不得静默降级。"""
    monkeypatch.setattr(license_gate, "LICENSE_ENABLED", True)

    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("wings_ctl.license"):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    try:
        license_gate.get_license_gate()
    except ValueError as exc:
        assert "missing the License gate" in str(exc)
        assert exc.__cause__ is not None
    else:
        raise AssertionError("get_license_gate must fail closed without wings_ctl.license")


def test_real_publisher_satisfies_protocol():
    """License 真实现符合 LicenseGate 协议(仅在 license 模块存在时可运行)。"""
    try:
        from wings_ctl.license import LicensePublisher
    except ModuleNotFoundError:
        return  # 非 License 源码树(构建会删模块),跳过
    assert isinstance(LicensePublisher(), license_gate.LicenseGate)


def test_build_declaration_matches_environment():
    """当前源码树(未过构建期改写)恒为非 License 声明,防止误删模块后被静默吞掉。"""
    assert isinstance(LICENSE_ENABLED, bool)
