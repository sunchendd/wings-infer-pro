"""引擎启动计划的统一分发入口。

特殊引擎由 ``EngineExtension`` 提供结构化启动计划；普通 argv 引擎继续沿用
现有适配器。CLI 和 ScriptBuilder 都通过本模块消费同一份计划，避免展示命令与
实际落盘脚本发生漂移。
"""

from __future__ import annotations

__all__ = [
    "EngineLaunchPlan",
    "build_launch_plan",
    "format_launch_dry_run_preview",
    "format_launch_preview",
    "format_launch_summary",
]

import shlex

from wings_ctl.core.models import ResolvedConfig
from wings_ctl.core.system_setup import render_source_command_blocks
from wings_ctl.engines.extension import EngineLaunchPlan, get_engine_extension
from wings_ctl.engines.vllm_adapter import build_argv, build_system_setup_source_commands


def _build_argv_launch_plan(resolved: ResolvedConfig) -> EngineLaunchPlan:
    """为未声明扩展启动能力的 argv 引擎保持历史行为。"""
    return EngineLaunchPlan(
        argv=build_argv(resolved.engine_config_traces, engine=resolved.engine),
        system_setup_source_commands=build_system_setup_source_commands(resolved.engine, resolved.system_setup),
    )


def build_launch_plan(resolved: ResolvedConfig) -> EngineLaunchPlan:
    """按扩展能力构造启动计划，公共层不识别引擎私有配置。"""
    builder = get_engine_extension(resolved.engine).launch_builder
    return builder(resolved) if builder is not None else _build_argv_launch_plan(resolved)


def format_launch_preview(resolved: ResolvedConfig) -> str:
    """生成人类可读的 dry-run 预览。"""
    plan = build_launch_plan(resolved)
    return plan.preview or shlex.join(plan.argv)


def format_launch_dry_run_preview(resolved: ResolvedConfig) -> str:
    """生成包含受支持 source 初始化命令的 dry-run 预览。"""
    plan = build_launch_plan(resolved)
    lines = []
    if plan.system_setup_source_commands:
        lines.extend(
            [
                "# System Setup source commands",
                *render_source_command_blocks(plan.system_setup_source_commands),
            ]
        )
    lines.append(plan.preview or shlex.join(plan.argv))
    return "\n".join(lines)


def format_launch_summary(resolved: ResolvedConfig) -> str:
    """按启动计划声明的标签与换行方式生成摘要。"""
    plan = build_launch_plan(resolved)
    preview = plan.preview or shlex.join(plan.argv)
    separator = "\n" if plan.preview_on_new_line else " "
    return f"{plan.preview_label}:{separator}{preview}"
