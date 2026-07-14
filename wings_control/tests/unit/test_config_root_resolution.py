from __future__ import annotations

from pathlib import Path

import pytest

from wings_ctl.loaders.config_root import resolve_config_root


def test_resolve_config_root_precedence_explicit_then_env_then_autodetect(tmp_path, monkeypatch):
    explicit_root = tmp_path / "explicit-config"
    env_root = tmp_path / "env-config"
    explicit_root.mkdir()
    env_root.mkdir()

    monkeypatch.setenv("WINGS_CTL_CONFIG_ROOT", str(env_root))
    assert resolve_config_root(explicit_root) == explicit_root

    assert resolve_config_root() == env_root

    monkeypatch.delenv("WINGS_CTL_CONFIG_ROOT", raising=False)
    autodetected = resolve_config_root()
    assert isinstance(autodetected, Path)
    assert autodetected.exists()


def test_resolve_config_root_raises_when_not_locatable(tmp_path, monkeypatch):
    """无 explicit、无 env、且向上找不到 pyproject → FileNotFoundError(定位失败)。

    把模块的 __file__ 指到一个无 pyproject 祖先的临时路径,触发 dev 模式兜底失败分支。
    """
    monkeypatch.delenv("WINGS_CTL_CONFIG_ROOT", raising=False)
    fake = tmp_path / "iso" / "config_root.py"
    monkeypatch.setattr("wings_ctl.loaders.config_root.__file__", str(fake))
    with pytest.raises(FileNotFoundError, match="config root"):
        resolve_config_root()
