"""pipeline — 编排层:hardware → engine → config → render → emit 单向流。

将完整的解析-渲染-审计流程封装为一次调用,供 CLI 和外部脚本使用。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from wings_ctl.audit.emitter import emit_audit
from wings_ctl.audit.startup_log import emit_startup_summary
from wings_ctl.core.config_resolver import resolve_config, resolve_custom_config
from wings_ctl.core.models import CustomConfigFile, PipelineRequest, ResolvedConfig, ResolvedEnv
from wings_ctl.engines.extension import get_engine_extension
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.license_gate import get_license_gate
from wings_ctl.loaders.config_root import resolve_config_root
from wings_ctl.rendering.script_builder import build_scripts
from wings_ctl.validators.engine_param_validator import validate_engine_params


def resolve_pipeline(request: PipelineRequest) -> ResolvedConfig:
    """resolve 阶段:config_root → hardware → version → config → 校验,**不落盘**。

    `run_pipeline`(落盘)与 CLI dry-run(只打印 argv)都走这里,
    确保两条路径使用同一套解析逻辑。

    Args:
        request: 流水线请求，包含解析目标、配置与硬件路径、用户输入、卡数和 placement；
            PD 场景还携带规范化 ``pd_input``，迁移期可携带 ``pd_role_missing_legacy``。

    Returns:
        ResolvedConfig(已含 accel 合并层 + param_validation,warn-only)。

    Raises:
        ValueError / FileNotFoundError / NotImplementedError: 配置缺失、拓扑不支持或校验失败。
    """
    resolved_root = resolve_config_root(request.config_root)
    hardware = resolve_hardware(request.hardware_info_path)
    extension = get_engine_extension(request.target.engine)
    # topology 能力必须在 ConfigResolver 前校验。否则 MindIE 收到 PD_ROLE 时会先
    # 进入当前 argv 引擎的 ProcessPlan 构建，扩展根本没有机会按自己的边界失败。
    if (
        extension.supported_topologies is not None
        and request.target.topology not in extension.supported_topologies
    ):
        supported = ", ".join(item.value for item in extension.supported_topologies)
        raise NotImplementedError(
            f"Engine {request.target.engine!r} does not support topology "
            f"{request.target.topology.value!r}; supported: {supported}"
        )
    engine_version = resolve_engine_version(
        resolved_root,
        hardware.hardware_family,
        engine=request.target.engine,
        require_exact=request.pd_input is not None,
    )
    env = ResolvedEnv(config_root=resolved_root, hardware=hardware, engine_version=engine_version)
    resolved = resolve_config(
        env,
        request.target,
        request.user_input,
        request.device_count,
        request.placement,
        request.pd_input,
    )
    if request.pd_role_missing_legacy:
        resolved.resolution_notes["pd_role_input"] = "missing_legacy_standard"
    # 基础 resolver 只产出通用 trace。扩展 prepare 返回的不透明领域计划只挂载
    # 到 ResolvedConfig，公共 Pipeline 不读取其中的 HCCL、EP 或 config 字段。
    if extension.prepare is not None:
        resolved.engine_state = extension.prepare(resolved, request)
    # 参数支持校验:只写审计结果,不修改最终参数。
    validate_engine_params(resolved, resolved_root)
    return resolved


def resolve_pipeline_custom(
    request: PipelineRequest,
    config_file: CustomConfigFile,
) -> ResolvedConfig:
    """resolve 阶段(custom config-file 路径):config_root → hardware → version → custom 解析。

    复用 ``resolve_pipeline`` 的 hardware/version 解析(纯上游,与 recipe 无关),config 解析走
    ``resolve_custom_config``(跳过 recipe,参数主源是 config-file);下游 validator 复用。
    """
    resolved_root = resolve_config_root(request.config_root)
    hardware = resolve_hardware(request.hardware_info_path)
    engine_version = resolve_engine_version(
        resolved_root, hardware.hardware_family, engine=request.target.engine
    )
    env = ResolvedEnv(config_root=resolved_root, hardware=hardware, engine_version=engine_version)
    resolved = resolve_custom_config(
        env,
        request.target,
        config_file=config_file,
        user_input=request.user_input,
        device_count=request.device_count,
        placement=request.placement,
        pd_input=request.pd_input,
    )
    # 参数支持校验:只写审计结果,不修改最终参数(与 resolve_pipeline 一致)。
    validate_engine_params(resolved, resolved_root)
    return resolved


def run_pipeline_custom(
    request: PipelineRequest,
    config_file: CustomConfigFile,
    output_dir: Path,
) -> Tuple[ResolvedConfig, Path, Path, Path]:
    """执行完整 resolve → render → audit 流水线(custom config-file 路径)。

    复用 ``run_pipeline`` 的三件产物落盘与启动摘要(build_scripts / emit_audit /
    emit_startup_summary 均纯消费 ResolvedConfig,零改动复用)。
    """
    publisher = get_license_gate()
    with publisher.lock(output_dir):
        publisher.invalidate(output_dir)
        resolved = resolve_pipeline_custom(request, config_file)
        publisher.enforce(request, resolved)
        artifact_dir, _ = publisher.artifact_dir(output_dir)

        start_path, repro_path = build_scripts(resolved, artifact_dir)
        audit_path = emit_audit(resolved, artifact_dir)
        publisher.publish(output_dir, None, artifact_dir)
    env_log = os.environ.get("WINGS_START_LOG")
    startup_log_target = Path(env_log) if env_log else Path("/var/log/wings/wings_start.log")
    emit_startup_summary(
        resolved=resolved,
        artifact_paths={
            "start": start_path,
            "repro": repro_path,
            "audit": audit_path,
            "output_dir": output_dir,
            "model_name": request.target.model_name,
        },
        log_path=startup_log_target,
        log_path_is_explicit=bool(env_log),
    )

    return resolved, start_path, repro_path, audit_path


def run_pipeline(request: PipelineRequest, output_dir: Path) -> Tuple[ResolvedConfig, Path, Path, Path]:
    """执行完整 resolve → render → audit 流水线。

    Args:
        request: 流水线请求；字段语义与 :func:`resolve_pipeline` 一致，PD 场景包含
            ``pd_input`` 和 ``pd_role_missing_legacy``。
        output_dir: 输出目录(start_command.sh / repro.sh / audit.json)。

    Returns:
        (ResolvedConfig, start_command.sh path, repro.sh path, audit.json path)
    """
    publisher = get_license_gate()
    with publisher.lock(output_dir):
        publisher.invalidate(output_dir)
        resolved = resolve_pipeline(request)
        publisher.enforce(request, resolved)
        extension = get_engine_extension(resolved.engine)
        if extension.control_prepare is not None:
            # Shared inputs must be complete before start_command.sh becomes visible
            # to the engine container.
            extension.control_prepare(resolved)

        artifact_dir, _ = publisher.artifact_dir(output_dir)
        start_path, repro_path = build_scripts(resolved, artifact_dir)
        audit_path = emit_audit(resolved, artifact_dir)
        publisher.publish(output_dir, None, artifact_dir)
    # WINGS_START_LOG 显式设了就用它(失败 WARN);否则默认 /var/log/wings(失败安静降级)。
    env_log = os.environ.get("WINGS_START_LOG")
    startup_log_target = Path(env_log) if env_log else Path("/var/log/wings/wings_start.log")
    emit_startup_summary(
        resolved=resolved,
        artifact_paths={
            "start": start_path,
            "repro": repro_path,
            "audit": audit_path,
            "output_dir": output_dir,
            "model_name": request.target.model_name,
        },
        log_path=startup_log_target,
        log_path_is_explicit=bool(env_log),
    )

    return resolved, start_path, repro_path, audit_path
