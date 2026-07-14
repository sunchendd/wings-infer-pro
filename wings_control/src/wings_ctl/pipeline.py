"""pipeline — 编排层:hardware → engine → config → render → emit 单向流。

将完整的解析-渲染-审计流程封装为一次调用,供 CLI 和外部脚本使用。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from wings_ctl.audit.emitter import emit_audit
from wings_ctl.audit.startup_log import emit_startup_summary
from wings_ctl.core.config_resolver import resolve_config
from wings_ctl.core.models import PipelineRequest, ResolvedConfig, ResolvedEnv
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.loaders.config_root import resolve_config_root
from wings_ctl.rendering.script_builder import build_scripts
from wings_ctl.validators.engine_param_validator import validate_engine_params


def resolve_pipeline(request: PipelineRequest) -> ResolvedConfig:
    """resolve 阶段:config_root → hardware → version → config → 校验,**不落盘**。

    `run_pipeline`(落盘)与 CLI dry-run(只打印 argv)都走这里,
    确保两条路径使用同一套解析逻辑。

    Args:
        request: 流水线请求(target / hardware_info_path / config_root / user_input / device_count / placement)。

    Returns:
        ResolvedConfig(已含 accel 合并层 + param_validation,warn-only)。

    Raises:
        ValueError / FileNotFoundError / NotImplementedError: 配置缺失、拓扑不支持或校验失败。
    """
    resolved_root = resolve_config_root(request.config_root)
    hardware = resolve_hardware(request.hardware_info_path)
    engine_version = resolve_engine_version(
        resolved_root, hardware.hardware_family, engine=request.target.engine
    )
    env = ResolvedEnv(config_root=resolved_root, hardware=hardware, engine_version=engine_version)
    resolved = resolve_config(
        env, request.target, request.user_input, request.device_count, request.placement
    )
    # 参数支持校验:只写审计结果,不修改最终参数。
    validate_engine_params(resolved, resolved_root)
    return resolved


def run_pipeline(
    request: PipelineRequest, output_dir: Path
) -> Tuple[ResolvedConfig, Path, Path, Path]:
    """执行完整 resolve → render → audit 流水线。

    Args:
        request: 流水线请求(target / hardware_info_path / config_root / user_input / device_count / placement)。
        output_dir: 输出目录(start_command.sh / repro.sh / audit.json)。

    Returns:
        (ResolvedConfig, start_command.sh path, repro.sh path, audit.json path)
    """
    resolved = resolve_pipeline(request)

    start_path, repro_path = build_scripts(resolved, output_dir)
    audit_path = emit_audit(resolved, output_dir)
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
