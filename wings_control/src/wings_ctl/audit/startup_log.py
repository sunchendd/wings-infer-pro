"""Startup summary log emitter (wings_start.log)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from wings_ctl.core.models import ResolvedConfig

logger = logging.getLogger(__name__)


def _build_summary_lines(
    resolved: ResolvedConfig,
    artifact_paths: Mapping[str, Any],
    target_log_path: Path,
) -> str:
    """把 ResolvedConfig 投影成人读的 ``[STARTUP]`` 摘要文本块(单一数据源,不重算)。

    Args:
        resolved: 解析结果(版本/硬件/引擎/model/user_cli/resolution_notes 由此投影)。
        artifact_paths: 三件产物路径 + ``model_name``(键:start/repro/audit/output_dir/model_name)。
        target_log_path: 最终写入的日志路径(仅用于在摘要里标 ``log=`` 字段)。

    Returns:
        一个以 ``[STARTUP]`` 开头、含时间戳分隔的多行文本块(末尾带换行)。
    """
    ts = datetime.now(timezone.utc).isoformat()
    notes = resolved.resolution_notes or {}
    requested_engine_version = resolved.engine_version.requested or "unset"
    resolved_config_version = resolved.engine_version.resolved or "unset"
    model_name = str(artifact_paths.get("model_name", "unset"))
    config_dir = notes.get("resolved_version_dir", "unset")
    model_config = notes.get("matched_model_yaml", "unset")

    start_path = Path(artifact_paths["start"])
    repro_path = Path(artifact_paths["repro"])
    audit_path = Path(artifact_paths["audit"])

    lines: list[str] = []
    lines.append(f"[STARTUP] ===== ts={ts} =====")
    lines.append(
        "[STARTUP] "
        f"ts={ts} hardware={resolved.hardware.hardware_family} "
        f"device={resolved.hardware.device} engine={resolved.engine} "
        f"requested_engine_version={requested_engine_version} "
        f"resolved_config_version={resolved_config_version} model={model_name}"
    )
    lines.append(f"[STARTUP] config_dir={config_dir}")
    lines.append(f"[STARTUP] model_config={model_config}")
    lines.append(f"[STARTUP] artifacts: start={start_path} repro={repro_path} audit={audit_path} log={target_log_path}")

    if (
        resolved.engine_version.is_fallback
        and resolved.engine_version.requested
        and resolved.engine_version.requested != resolved.engine_version.resolved
    ):
        lines.append(
            "[STARTUP] WARNING: "
            f"ENGINE_VERSION={resolved.engine_version.requested} "
            f"在 {resolved.engine} 下无精确配置, 回退到最新支持版本 "
            f"{resolved.engine_version.resolved or 'unset'}"
        )

    rows = resolved.user_cli_params or []
    applied_count = sum(1 for row in rows if row.get("status") == "applied")
    dropped_rows = [row for row in rows if row.get("status") == "dropped"]
    lines.append(f"[STARTUP] user_cli_params: applied={applied_count} dropped={len(dropped_rows)}")
    for row in dropped_rows:
        key = row.get("key", "<unknown>")
        reason = row.get("reason", "")
        lines.append(f"[STARTUP] dropped: {key} reason={reason}")

    dc = notes.get("device_count", "unset")
    dc_status = notes.get("device_count_status")
    if dc_status:
        lines.append(
            "[STARTUP] "
            f"device_count={dc} → DP={notes.get('device_count_resolved_dp', '?')} "
            f"(strategy_device_count, TP={notes.get('device_count_tp', '?')} 静态, status={dc_status})"
        )
    else:
        lines.append(f"[STARTUP] device_count={dc} (未下发或未触发 DP 协调)")

    # PD 摘要只投影规范 topology/process plan，不重算 rank、端口或卡组。
    if resolved.pd_topology and resolved.process_plan:
        pd = resolved.pd_topology
        plan = resolved.process_plan
        lines.append(
            "[STARTUP] pd "
            f"role={pd.role.value} pd_index={pd.instance_index} "
            f"member={pd.member_index + 1}/{len(pd.placement.node_ips or [])} "
            f"layout={plan.layout} lifecycle={plan.lifecycle}"
        )
        lines.append(
            "[STARTUP] pd allocation "
            f"local_dp={pd.dp_size_local} ranks={pd.rank_start}..{pd.rank_end_exclusive - 1} "
            f"endpoints={','.join(plan.endpoints)}"
        )
        recommendation_status = notes.get("pd_recipe_recommendation_status")
        if recommendation_status:
            lines.append(
                "[STARTUP] pd recipe_recommendation "
                f"status={recommendation_status} "
                f"shape_match={notes.get('pd_recipe_shape_match', '?')} "
                f"role_member_count_match={notes.get('pd_recipe_role_member_count_match', '?')}"
            )

    # multi_node 摘要:未注入时展示占位视图;已注入时展示本 Pod 角色和并行信息。
    if resolved.nodes:
        roles = ",".join(n.role for n in resolved.nodes)
        lines.append(
            f"[STARTUP] multi_node: nodes={len(resolved.nodes)} roles=[{roles}] injection=pending(无运行时上下文)"
        )
    elif notes.get("multi_node_injection_status") == "injected":
        dp_status = notes.get("multinode_dp_status", "template")
        lines.append(
            "[STARTUP] multi_node: "
            f"role={notes.get('multi_node_role', '?')} index={notes.get('multi_node_index', '?')} "
            f"pod_count={notes.get('multi_node_pod_count', '?')} injection=injected "
            f"(dp={notes.get('multinode_dp_resolved_dp', '?')} status={dp_status})"
        )
    # EngineParamValidator:warn-only 支持参数校验摘要。None=未校验 → 不出行。
    pv = resolved.param_validation
    if pv is not None:
        lines.append(
            "[STARTUP] param_validation "
            f"policy={pv.policy} "
            f"supported_params_file={pv.supported_params_file or 'MISSING'} "
            f"status={pv.status}"
        )
        for item in pv.unsupported:
            node = item.get("node")  # multi_node 才有;standalone 无此键 → 不出 node= 段
            node_seg = f"node={node} " if node else ""
            lines.append(
                "[STARTUP] unsupported_param action=warn "
                f"{node_seg}param={item.get('param')} rendered_as={item.get('rendered_as')} "
                f"source={item.get('source_file')}#{item.get('source_path')}"
            )

    lines.append("[STARTUP] ===== end =====")
    lines.append("")
    return "\n".join(lines)


def _append_block(path: Path, content: str) -> None:
    """**追加**写一个摘要块到 host 日志(自动建父目录)。

    用追加(``"a"``)而非覆盖,使同一 host 日志累积每次启动的摘要。

    Args:
        path: 目标日志文件路径。
        content: 待追加的文本块(由 _build_summary_lines 产出)。

    Raises:
        OSError: 目录不可建 / 文件不可写(由调用方 emit_startup_summary 捕获并降级)。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(content)


def emit_startup_summary(
    resolved: ResolvedConfig,
    artifact_paths: Mapping[str, Any],
    log_path: Path,
    log_path_is_explicit: bool = False,
) -> Path:
    """产出第 4 类输出 wings_start.log 的启动摘要块(host 人读日志)。

    写入策略(**鲁棒,绝不因日志失败中断流水线**):
        1. 优先写 ``log_path``(默认 ``/var/log/wings/wings_start.log``,可由 ``WINGS_START_LOG`` env 覆盖);
        2. 不可写(权限/目录)→ 降级到 ``<output_dir>/wings_start.log``;
        3. 降级也失败 → 不抛异常,继续。

    日志噪音控制:默认路径(``/var/log/wings``)在 dev/非 root 下不可写是常态,
    降级走 **INFO**(安静);仅当用户**显式**设了 ``WINGS_START_LOG`` 却写不进时才 **WARNING**
    (用户指定的路径失败值得警示)。

    Args:
        resolved: 解析结果(摘要数据源)。
        artifact_paths: 三件产物路径 + ``model_name`` + ``output_dir``(降级落点)。
        log_path: 首选日志路径(由 pipeline 据 ``WINGS_START_LOG`` env / 默认值给出)。
        log_path_is_explicit: ``log_path`` 是否来自用户显式 ``WINGS_START_LOG``
            (True→失败 WARNING;False=默认路径→失败 INFO,安静降级)。

    Returns:
        实际写入的日志路径(首选或降级路径)。

    Note:
        ``resolved.param_validation`` 非空时,
        ``_build_summary_lines`` 追加 warn-only 摘要行(warn 不删):
            ``[STARTUP] param_validation policy=warn_only supported_params_file=<...> status=<...>``
            ``[STARTUP] unsupported_param action=warn param=<k> rendered_as=... source=...``
    """
    output_dir = Path(artifact_paths["output_dir"])
    requested_log_path = Path(log_path)

    try:
        content = _build_summary_lines(resolved, artifact_paths, requested_log_path)
        _append_block(requested_log_path, content)
        return requested_log_path
    except OSError as exc:
        fallback_path = output_dir / "wings_start.log"
        # 默认路径不可写=dev/非 root 常态 → INFO 安静降级;显式路径失败 → WARNING。
        log_fn = logger.warning if log_path_is_explicit else logger.info
        log_fn(
            "startup log 写入 %s 失败(%s),已降级到 %s",
            requested_log_path,
            exc,
            fallback_path,
        )
        try:
            content = _build_summary_lines(resolved, artifact_paths, fallback_path)
            _append_block(fallback_path, content)
        except OSError as fallback_exc:
            logger.warning(
                "Failed to write fallback startup log to %s (%s); continuing without startup log",
                fallback_path,
                fallback_exc,
            )
        return fallback_path
