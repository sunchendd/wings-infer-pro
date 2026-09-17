"""子命令注册表。

每个子命令模块实现 ``Command`` 协议并在本文件 ``COMMANDS`` 注册;
入口 aiperf.py 只查表分发,不认识具体命令。新增能力 = 新模块 + 一行注册。
"""

from __future__ import annotations

from typing import Callable, Dict, List

from config import AiperfConfig

CommandFn = Callable[[List[str], AiperfConfig], int]


class Command:
    """子命令协议:``run(argv, config) -> exit_code``。"""

    name: str
    help: str

    def run(self, argv: List[str], config: AiperfConfig) -> int:
        raise NotImplementedError


def _register(registry: Dict[str, Command], command: Command) -> None:
    if command.name in registry:
        raise RuntimeError(f"duplicate aiperf command: {command.name}")
    registry[command.name] = command


def build_registry() -> Dict[str, Command]:
    """实例化全部子命令;此函数是命令集的唯一事实来源。"""
    from cmd_license import LicenseCommand

    registry: Dict[str, Command] = {}
    _register(registry, LicenseCommand())
    return registry


COMMANDS: Dict[str, Command] = build_registry()
