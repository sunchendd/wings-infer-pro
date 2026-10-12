"""__main__ 的 Windows dry-run fcntl mock 单测。

覆盖 _mock_fcntl_on_windows_dry_run：
- Windows + dry-run → 向 sys.modules 注入 mock fcntl（ioctl 恒抛 OSError）。
- 非 Windows → 不注入（保留真实/已有 fcntl）。
- Windows 但非 dry-run → 不注入。

注：__main__.py 顶层会执行 _mock_fcntl_on_windows_dry_run() 并导入 cli，
因此用 importlib 加载模块源码，通过控制 sys.platform / sys.argv 决定顶层行为。
非 dry-run 场景顶层导入 cli 会因 fcntl 缺失失败，故先注入占位 fcntl 模拟
"已有 fcntl" 的环境，再验证 mock 不覆盖它。
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_MAIN_PATH = Path(__file__).resolve().parents[2] / "src" / "wings_ctl" / "__main__.py"


def _install_fake_fcntl(monkeypatch) -> types.ModuleType:
    """向 sys.modules 注入一个占位 fcntl，模拟"平台已有 fcntl"的环境。"""
    fake = types.ModuleType("fcntl")

    def _fake_ioctl(*_args, **_kwargs):
        return b"fake"

    fake.ioctl = _fake_ioctl
    monkeypatch.setitem(sys.modules, "fcntl", fake)
    return fake


def _load_main_module(monkeypatch, platform: str, argv: list[str]) -> None:
    """加载 __main__ 模块源码，控制平台与 argv（副作用：执行模块顶层代码）。"""
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(sys, "argv", argv)
    spec = importlib.util.spec_from_file_location("wings_ctl.__main__", _MAIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def test_windows_dry_run_injects_fcntl_mock(monkeypatch):
    """Windows + dry-run → sys.modules['fcntl'] 被注入，ioctl 恒抛 OSError。"""
    monkeypatch.delitem(sys.modules, "fcntl", raising=False)
    _load_main_module(monkeypatch, platform="win32", argv=["wings-ctl", "--dry-run"])
    fcntl = sys.modules.get("fcntl")
    assert fcntl is not None, "Windows dry-run 应注入 mock fcntl"
    with pytest.raises(OSError):
        fcntl.ioctl(0, 0, b"")


def test_non_windows_does_not_inject_fcntl(monkeypatch):
    """非 Windows（如 Linux）→ 不注入 mock fcntl，保留已有 fcntl。"""
    fake = _install_fake_fcntl(monkeypatch)
    _load_main_module(monkeypatch, platform="linux", argv=["wings-ctl", "--dry-run"])
    assert sys.modules["fcntl"] is fake, "非 Windows 不应覆盖已有 fcntl"


def test_windows_non_dry_run_does_not_inject_fcntl(monkeypatch):
    """Windows 但非 dry-run → 不注入 mock fcntl（正常启动保持原样）。"""
    fake = _install_fake_fcntl(monkeypatch)
    _load_main_module(monkeypatch, platform="win32", argv=["wings-ctl"])
    assert sys.modules["fcntl"] is fake, "非 dry-run 不应覆盖已有 fcntl"
