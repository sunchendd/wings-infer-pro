"""``aiperf license`` 子命令:证书与 ESN 查询。

只做查询(读证书字符串与 ESN),不验签、不依赖 docker;验签由
wings-control 容器在启动门禁中完成。
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List

from commands import Command
from config import AiperfConfig
from errors import LicenseQueryError
from license_info import LicenseFile, LicenseQueryResult

# 查询结果是对外交付数据,必须走 stdout(可管道/可重定向);logging 默认流是
# stderr,这里显式指到 stdout。错误仍由入口的 aiperf logger 走 stderr。
_result_logger = logging.getLogger("aiperf.license.result")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(message)s"))
_result_logger.addHandler(_handler)
_result_logger.propagate = False

# ESN 规范化边界:长度上限与字符集(ASCII 字母数字),与 checker.c 口径一致。
ESN_MAX_LENGTH = 40


def resolve_unique_license(license_dir: Path) -> Path:
    """定位唯一证书:零个/多个都报错(多个时列出文件名)。"""
    candidates = sorted(license_dir.glob("*.xml")) if license_dir.is_dir() else []
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise LicenseQueryError(
            f"multiple license files in {license_dir}: {names}; exactly one is allowed"
        )
    if not candidates:
        raise LicenseQueryError(f"no license file (*.xml) in {license_dir}")
    return candidates[0]


def _esn_is_well_formed(value: str) -> bool:
    """ESSN 形状校验:非空、不超长、ASCII 字母数字(内部空白不删——删了再匹配等于放宽)。"""
    return bool(value) and len(value) <= ESN_MAX_LENGTH and value.isalnum() and value.isascii()


def get_esn(path: Path) -> str:
    """读宿主机主板序列号并规范化为 ESN。

    只去首尾空白、转大写;内容必须是 1-40 位 ASCII 字母数字,其余一律拒绝。
    """
    try:
        value = path.read_text(encoding="utf-8").strip().upper()
    except OSError as exc:
        raise LicenseQueryError(f"failed to read board serial: {path} ({exc})") from exc
    if not _esn_is_well_formed(value):
        raise LicenseQueryError("board serial must contain 1-40 uppercase letters or digits")
    return value


def query(config: AiperfConfig) -> LicenseQueryResult:
    """取唯一证书内容 + 宿主机 ESN(一次查询的全部产物)。"""
    path = resolve_unique_license(config.license_dir)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LicenseQueryError(f"failed to read license file: {path} ({exc})") from exc
    return LicenseQueryResult(
        license_file=LicenseFile(path=path, content=content),
        esn=get_esn(config.board_serial_path),
    )


class LicenseCommand(Command):
    name = "license"
    help = "license query (show certificate and host ESN)"

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="aiperf license", description=self.help)
        sub = parser.add_subparsers(dest="license_command", required=True)
        show = sub.add_parser("show", help="print license file path, content and host ESN")
        show.add_argument(
            "--esn-only",
            action="store_true",
            help="print only the host ESN (for scripts)",
        )
        return parser

    def run(self, argv: List[str], config: AiperfConfig) -> int:
        args = self.build_parser().parse_args(argv)
        result = query(config)
        if getattr(args, "esn_only", False):
            _result_logger.info("%s", result.esn)
        else:
            _result_logger.info("%s", result.render())
        return 0
