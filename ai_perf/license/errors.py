"""AIPerf 工具错误体系。

所有业务模块抛 ``AiperfError`` 子类,入口按 ``exit_code`` 转退出码;
退出码是 CLI 契约,已占用的值不得变更。
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """稳定退出码;新增只追加,不复用旧值。"""

    OK = 0
    USAGE = 1  # 命令/参数用法错误
    LICENSE = 2  # license 查询失败(缺失/多份/ESN 非法等)
    CONFIG = 3  # 配置文件缺失或不可解析
    RUNTIME = 4  # 未预期的运行期错误


class AiperfError(RuntimeError):
    """工具内可预期错误基类;``exit_code`` 决定 CLI 退出码。"""

    exit_code: ExitCode = ExitCode.RUNTIME


class LicenseQueryError(AiperfError):
    """license 查询失败:目录无证书、多证书、ESN 不可读等。"""

    exit_code = ExitCode.LICENSE


class ConfigError(AiperfError):
    """配置文件缺失、JSON 语法错误或字段形状非法。"""

    exit_code = ExitCode.CONFIG
