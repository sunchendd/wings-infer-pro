"""StartupAuditEmitter — 从 ResolvedConfig 产出 audit.json。

输入: ResolvedConfig, output_dir (Path)
输出: 写入 audit.json 到 output_dir

audit.json 结构:
- 每个参数的完整 events 链
- 能回答"该参数最终值是多少 / 来自哪层哪文件 / 被哪层覆盖过"
- 包含版本回退警告 (requested ≠ resolved)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from wings_ctl.core.models import ResolvedConfig, ResolvedNode, SystemSetup, TracedValue


def _serialize_traced_value(traced: TracedValue) -> Dict[str, Any]:
    """将 TracedValue 序列化为 JSON 友好的 dict。"""
    return {
        "final_value": traced.final_value,
        "final_layer": traced.final_layer,
        "source_file": traced.source_file,
        "source_path": traced.source_path,
        "events": [
            {
                "action": e.action,
                "layer": e.layer,
                "value": e.value,
                "source_file": e.source_file,
                "source_path": e.source_path,
            }
            for e in traced.events
        ],
    }


def _serialize_system_setup(system_setup: Optional[SystemSetup]) -> Optional[Dict[str, Any]]:
    """将 SystemSetup 序列化为 JSON 友好 dict;``None`` → ``None``。

    顶层 system_setup 与 multi_node 各 node 的 system_setup 共用本序列化(单一入口,
    避免字段/顺序两处漂移)。字段名与顺序保持不变:
    ``sysctls`` / ``sysfs_writes`` / ``commands`` / ``source_file`` / ``source_path``。

    Args:
        system_setup: 待序列化的 SystemSetup;``None`` 表示该节点/顶层无 system_setup。

    Returns:
        序列化 dict;入参为 ``None`` 时返回 ``None``。
    """
    if system_setup is None:
        return None
    return {
        "sysctls": system_setup.sysctls,
        "sysfs_writes": system_setup.sysfs_writes,
        "commands": system_setup.commands,
        "source_file": system_setup.source_file,
        "source_path": system_setup.source_path,
    }


def _serialize_traced_mapping(traces: Dict[str, TracedValue]) -> Dict[str, Any]:
    """将一组带来源追踪的参数按原插入顺序序列化。

    Args:
        traces: 参数名到 TracedValue 的映射。

    Returns:
        JSON 友好的参数追踪映射。
    """
    serialized: Dict[str, Any] = {}
    for key, traced in traces.items():
        serialized[key] = _serialize_traced_value(traced)
    return serialized


def _serialize_resolved_node(node: ResolvedNode) -> Dict[str, Any]:
    """将 multi_node 占位视图中的单个节点序列化。

    Args:
        node: 待写入 audit.nodes[] 的节点解析结果。

    Returns:
        JSON 友好的节点字典。字段顺序与原 audit 产物保持一致。
    """
    return {
        "role": node.role,
        "index": node.index,
        "source_prefix": node.source_prefix,
        "engine_config": _serialize_traced_mapping(node.engine_config_traces),
        "env": _serialize_traced_mapping(node.env_traces),
        "system_setup": _serialize_system_setup(node.system_setup),
    }


def _build_audit_dict(resolved: ResolvedConfig) -> Dict[str, Any]:
    """构建完整的 audit 字典。"""
    audit: Dict[str, Any] = {}

    # 版本信息 + 回退警告
    version_info: Dict[str, Any] = {
        "engine": resolved.engine,
        "requested_engine_version": resolved.engine_version.requested,
        "resolved_config_version": resolved.engine_version.resolved,
        "is_fallback": resolved.engine_version.is_fallback,
    }
    if resolved.engine_version.is_fallback and resolved.engine_version.requested:
        version_info["config_resolution_warning"] = (
            f"Requested version '{resolved.engine_version.requested}' not found; "
            f"fell back to '{resolved.engine_version.resolved}'. "
            "The running configuration may not exactly match the requested version."
        )
    audit["version"] = version_info

    # 硬件信息
    extra_details = {
        k: v
        for k, v in resolved.hardware.raw.items()
        if k not in {"hardware_family", "device"}
    }
    hardware_entry = {
        "hardware_family": resolved.hardware.hardware_family,
        "device": resolved.hardware.device,
    }
    if extra_details:
        hardware_entry["details"] = extra_details
    audit["hardware"] = hardware_entry

    # 拓扑
    audit["topology"] = resolved.topology.value

    # 源文件
    audit["source_files"] = resolved.source_files

    # engine_config 完整追踪
    audit["engine_config"] = _serialize_traced_mapping(resolved.engine_config_traces)

    # env 完整追踪
    audit["env"] = _serialize_traced_mapping(resolved.env_traces)

    # user_cli_params: 单数组含全量(status∈{applied,dropped},dropped 带 reason)。
    # 不另开 dropped_user_params 数组——dropped 项可由 status 过滤得出,避免双写漂移。
    if resolved.user_cli_params:
        audit["user_cli_params"] = list(resolved.user_cli_params)

    # 解析注记(如 platform_default: absent)
    if resolved.resolution_notes:
        audit["resolution_notes"] = dict(resolved.resolution_notes)

    # system_setup(仅来自模型场景层)。保留 if 守卫:无 system_setup 时**不写该键**
    # (与旧行为一致——非 multi_node 顶层 system_setup 缺失时 audit 里无此键,而非 null)。
    if resolved.system_setup:
        audit["system_setup"] = _serialize_system_setup(resolved.system_setup)

    # multi_node 占位视图(无运行时上下文):顶层 engine_config/env 为空,
    # 真实视图在 nodes 数组。已完成注入时 nodes=None,本 Pod 升为顶层,集群信息见 resolution_notes。
    if resolved.nodes:
        audit["multi_node_injection_status"] = "pending_runtime_context"
        nodes = []
        for node in resolved.nodes:
            nodes.append(_serialize_resolved_node(node))
        audit["nodes"] = nodes

    # wings-accel(智能加速)诊断:非空时写入,供排查"加速产出了什么"。
    # 内容为各 OutputParams 的 wings_accel_params + 顶层汇总;空(未接通/关闭)→ 不写。
    if resolved.accel.audit:
        audit["wings_accel"] = resolved.accel.audit

    # EngineParamValidator:warn-only 支持参数校验结果。非空即写(含 skip 兜底态),
    # would-warn 参数带来源链;供 lint/CI/offline 消费(runtime 只 warn 不删)。
    if resolved.param_validation is not None:
        pv = resolved.param_validation
        audit["param_validation"] = {
            "policy": pv.policy,
            "supported_params_file": pv.supported_params_file,
            "status": pv.status,
            "unsupported": pv.unsupported,
        }

    return audit


def emit_audit(
    resolved: ResolvedConfig,
    output_dir: Path,
) -> Path:
    """生成 audit.json 并写入 output_dir。

    Returns:
        audit.json 文件路径。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_dict = _build_audit_dict(resolved)

    audit_path = output_dir / "audit.json"
    audit_path.write_text(
        json.dumps(audit_dict, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return audit_path
