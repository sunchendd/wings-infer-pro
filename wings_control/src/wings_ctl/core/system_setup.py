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


def render_source_command_blocks(source_commands: Iterable[str]) -> List[str]:
    """把已校验的 source 命令渲染为可执行块。

    启动脚本以 ``set -euo pipefail`` 进入，厂商 set_env.sh 可能读取未定义变量
    (如 ``ZSH_VERSION``) 或在部分镜像缺失。整个 source 段只在开头 ``set +u``、
    结尾 ``set -u`` 关闭一次 nounset，再对每条 source 做 ``-f`` 守卫：缺失时向
    stderr 打印 WARN 并跳过，``if`` 分支返回 0，不中断脚本继续执行，也不静默失败。

    Args:
        source_commands: 已由 ``extract_source_commands`` 校验过的 source 命令列表。

    Returns:
        可直接写入 bash 脚本的行(不含收尾空行)。
    """
    lines: List[str] = []
    for command in source_commands:
        try:
            tokens = shlex.split(command, comments=True, posix=True)
        except ValueError:
            tokens = []
        if len(tokens) != 2 or tokens[0] != "source" or not tokens[1].startswith("/"):
            # 上游 extract_source_commands 只产出严格 source <绝对路径> 行，
            # 此分支通常不触发；原样还原其余输入，避免被静默丢弃。
            lines.append(command)
            continue
        path = tokens[1]
        quoted = shlex.quote(path)
        lines.append(f"if [ -f {quoted} ]; then")
        lines.append(f"  {command}")
        lines.append("else")
        lines.append(f"  echo {shlex.quote(f'WARN: system_setup source not found, skipping: {path}')} >&2")
        lines.append("fi")
    if not lines:
        return []
    return ["set +u", *lines, "set -u"]
