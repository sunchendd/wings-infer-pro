"""MindIE 旧导入路径的迁移期兼容 facade。

真实实现已迁入 ``wings_ctl.engines.mindie`` 领域包。这里仅保留当前测试和外部调用方
使用的函数签名，不再承载 topology、ranktable、配置或 runtime 逻辑；新代码应通过
``EngineExtension`` 进入。待调用方迁移完成后可整体删除本文件。
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_MINDIE_WORK_DIR",
    "SUPPORTED_MINDIE_VERSION",
    "build_config_overrides",
    "build_launch_parts",
    "build_trace_comment_lines",
    "validate_resolved_config",
]

from typing import Any, Dict, List, Tuple

from wings_ctl.core.models import ResolvedConfig
from wings_ctl.engines.mindie.common import (
    DEFAULT_MINDIE_WORK_DIR,
    SUPPORTED_MINDIE_VERSION,
)
from wings_ctl.engines.mindie.config_v230 import build_config_overrides as _project
from wings_ctl.engines.mindie.extension import (
    _plan_from_resolved,
    build_trace_comment_lines,
    validate as _validate,
)
from wings_ctl.engines.mindie.runtime import build_launch_plan as _build_launch_plan


def validate_resolved_config(resolved: ResolvedConfig) -> None:
    """兼容旧 validator 入口；失败策略仍为 fail-fast。"""
    _validate(resolved)


def build_config_overrides(resolved: ResolvedConfig) -> Dict[str, Any]:
    """兼容旧配置投影入口。"""
    return _project(_plan_from_resolved(resolved))


def build_launch_parts(resolved: ResolvedConfig) -> Tuple[List[str], List[str], str]:
    """兼容旧 ``(argv, pre_start, preview)`` 返回契约。"""
    launch = _build_launch_plan(_plan_from_resolved(resolved))
    return launch.argv, launch.pre_start_lines, launch.preview
