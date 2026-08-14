"""生成脚本的无容器副作用命令执行测试工具。"""

from __future__ import annotations

import subprocess
from pathlib import Path


def run_vllm_command_as_echo(script_path: Path) -> str:
    """抽取 vLLM 命令并通过 bash echo 验证其 shell quoting。

    生产 ``start_command.sh`` 还包含 analyzer、安装和 pre-serve 等容器内步骤；
    本机测试只验证引擎命令，避免依赖 ``/shared-volume`` 和 ``/var/log/wings``。

    Args:
        script_path: ``start_command.sh`` 或 ``repro.sh`` 路径。

    Returns:
        bash 实际解析后输出的单行 ``vllm serve ...`` 命令。

    Raises:
        AssertionError: 脚本没有唯一的 vLLM 命令，或 echo 输出不唯一。
        subprocess.CalledProcessError: 提取出的命令不满足 bash 语法或执行失败。
    """
    command = next(
        (
            line
            for line in script_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("vllm serve ") or line.startswith("exec vllm serve ")
        ),
        None,
    )
    if command is None:
        raise AssertionError(f"missing vllm serve command: {script_path}")
    if command.startswith("exec "):
        command = command.removeprefix("exec ")
    command = command.removesuffix(" &")

    echo_path = script_path.with_name(f"echo_{script_path.name}")
    echo_path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\necho {command}\n", encoding="utf-8")
    output = subprocess.run(
        ["bash", str(echo_path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    command_lines = [line for line in output.splitlines() if line.startswith("vllm serve ")]
    if len(command_lines) != 1:
        raise AssertionError(f"expected one vllm serve line, got {len(command_lines)}")
    return command_lines[0]
