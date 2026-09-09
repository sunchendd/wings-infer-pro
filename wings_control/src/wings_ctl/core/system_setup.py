"""system_setup 中可安全执行的 source 初始化命令解析。"""

from __future__ import annotations

import shlex
from typing import Any, Iterable, List


def extract_source_commands(commands: Iterable[Any], *, context: str) -> List[str]:
    """提取严格形如 ``source <absolute-path>`` 的命令并安全重渲染。

    非 source commands 保持由调用方忽略；source 语法错误、参数个数异常或相对路径
    则立即失败，避免 dry-run 与最终脚本对同一 YAML 的接受范围不一致。

    Args:
        commands: ``system_setup.commands`` 原始列表。
        context: 出错时标识调用位置的文本。

    Returns:
        可直接写入 bash 脚本的 source 命令，保持原始顺序。
    """
    rendered: List[str] = []
    for command in commands:
        if not isinstance(command, str):
            continue
        try:
            tokens = shlex.split(command, comments=True, posix=True)
        except ValueError as exc:
            if command.lstrip().startswith("source"):
                raise ValueError(f"Invalid {context} source command: {command!r}") from exc
            continue
        if not tokens or tokens[0] != "source":
            continue
        if len(tokens) != 2 or not tokens[1].startswith("/"):
            raise ValueError(
                f"{context} source command must be 'source <absolute-path>': {command!r}"
            )
        rendered.append(f"source {shlex.quote(tokens[1])}")
    return rendered
