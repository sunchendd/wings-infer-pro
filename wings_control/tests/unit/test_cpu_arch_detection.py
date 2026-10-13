"""v2 ``cpu_arch`` ctx 值探测单测。

覆盖:``_detect_cpu_arch`` 用 ``platform.machine()`` 探测并归一化(``amd64`` → ``x86_64``)。

注:本模块 import 自 wings_ctl.core.config_resolver(经 env_utils 依赖 fcntl),
仅 Linux 可运行;Windows 环境无法导入(既有环境限制)。
"""

from __future__ import annotations

import platform

import pytest

from wings_ctl.core.config_resolver import _detect_cpu_arch


@pytest.mark.parametrize(
    ("machine", "expected"),
    [
        ("x86_64", "x86_64"),
        ("AMD64", "x86_64"),
        ("amd64", "x86_64"),
        ("aarch64", "aarch64"),
        ("AARCH64", "aarch64"),
        ("arm64", "arm64"),
    ],
)
def test_detect_cpu_arch_normalizes_machine(monkeypatch, machine, expected):
    monkeypatch.setattr(platform, "machine", lambda: machine)
    assert _detect_cpu_arch() == expected
