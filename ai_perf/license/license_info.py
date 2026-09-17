"""License 查询数据结构。

宿主机侧只读不验签:结构承载"证书文件 + 宿主机 ESN"的查询结果,
验签属于 wings-control 容器内的启动门禁,不在此层。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LicenseFile:
    """唯一证书定位结果。"""

    path: Path
    content: str


@dataclass(frozen=True)
class LicenseQueryResult:
    """``license show`` 的输出载体:证书 + ESN 一次取齐。"""

    license_file: LicenseFile
    esn: str

    def render(self) -> str:
        """人类可读输出(与原 MVP 输出格式保持一致)。"""
        return (
            f"license_file: {self.license_file.path}\n"
            f"esn: {self.esn}\n"
            f"license:\n{self.license_file.content}"
        )
