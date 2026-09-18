#!/usr/bin/env python3
"""AIPerf 命令行总入口。

只做三件事:解析全局参数、按命令表分发子命令、把模块错误转成退出码。
业务逻辑一律放各子命令模块(如 cmd_license.py),新增能力只需实现
``Command`` 协议并在 ``commands.py`` 注册,入口零改动。
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

# 同目录模块(config/errors/commands/cmd_*)不构成包,须把脚本目录加入
# sys.path 才可导入。用 append 而非 insert(0):不抢占标准库/站点包的模块名,
# 避免与已加载同名模块冲突(如 config);必须在下方 import 前执行。
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

from config import AiperfConfig, load_config
from errors import AiperfError, ExitCode

logger = logging.getLogger("aiperf")


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 骨架:全局参数 + 子命令占位,子命令参数由各模块自填。"""
    parser = argparse.ArgumentParser(
        prog="aiperf",
        description="AIPerf host-side toolkit (license query, deployment helpers)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to aiperf.json (default: search ./aiperf.json, /etc/aiperf/aiperf.json)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return parser


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args, rest = parser.parse_known_args(argv)
    _setup_logging(args.verbose)

    from commands import COMMANDS

    if not rest:
        parser.print_help()
        return int(ExitCode.USAGE)

    name, sub_rest = rest[0], rest[1:]
    command = COMMANDS.get(name)
    if command is None:
        logger.error("[AIPERF] ERROR: unknown command '%s'; available: %s", name, ", ".join(sorted(COMMANDS)))
        return int(ExitCode.USAGE)

    try:
        config = load_config(args.config)
    except AiperfError as exc:
        logger.error("[AIPERF] ERROR: %s", exc)
        return int(exc.exit_code)

    try:
        return command.run(sub_rest, config)
    except AiperfError as exc:
        logger.error("[AIPERF] ERROR: %s", exc)
        return int(exc.exit_code)
    except KeyboardInterrupt:
        logger.error("[AIPERF] ERROR: interrupted")
        return int(ExitCode.RUNTIME)
    except Exception as exc:  # 进程边界:未预期异常统一兜底,保留原因链。
        logger.exception("[AIPERF] ERROR: unexpected failure: %s", exc)
        return int(ExitCode.RUNTIME)


if __name__ == "__main__":
    raise SystemExit(main())
