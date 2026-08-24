"""MindIE 领域能力的唯一公共装配入口。

MindIE 复用的是 ``EngineExtension`` 的调用协议，而不是 vLLM/SGLang 的并行算法。
本模块按 topology 选择单机或双节点 resolver，并向公共层提供参数、校验、启动、
health 和 progress 能力；ranktable、tp/dp 与 HCCL 仍封闭在本包内部。
"""

from __future__ import annotations

import json
import logging
from typing import Union

from wings_ctl.core.models import ParamValidationResult, PipelineRequest, ResolvedConfig
from wings_ctl.core.topology import Topology
from wings_ctl.engines.extension import (
    EngineExtension,
    EngineLaunchPlan,
    HealthProfile,
    ParameterTranslationProfile,
    ProgressProfile,
)
from wings_ctl.engines.mindie.config_v230 import (
    MINDIE_MANAGEMENT_HOST,
    MINDIE_MANAGEMENT_PORT,
    build_full_config,
)
from wings_ctl.engines.mindie.dual_node import (
    MindieDualNodePlan,
    resolve_dual_node_plan,
)
from wings_ctl.engines.mindie.runtime import (
    MINDIE_CONFIG_TARGET_PATH,
    build_launch_plan as build_runtime_launch_plan,
    prepare_control_ranktable,
)
from wings_ctl.engines.mindie.standalone import (
    MindieStandalonePlan,
    device_count_transform,
    resolve_standalone_plan,
)


logger = logging.getLogger(__name__)
MindiePlan = Union[MindieStandalonePlan, MindieDualNodePlan]


_PARAMETER_MAPPING = {
    "model_path": "model",
    "model_name": "served_model_name",
    "input_length": "max_input_token_len",
    "output_length": "max_iter_times",
    "max_model_len": "max_seq_len",
    "gpu_memory_utilization": "npu_memory_fraction",
    "max_num_seqs": None,
    "max_num_batched_tokens": None,
    "enable_auto_think_choice": None,
    "enable_auto_tool_choice": None,
    "enable_smartqos": None,
    "enable_otlp_traces": None,
    "enable_metrics": None,
    "dtype": None,
    "kv_cache_dtype": None,
    "quantization_param_path": None,
    "block_size": None,
    "seed": None,
    "enable_chunked_prefill": None,
}

_DROP_REASONS = {
    "max_num_seqs": "mindie_scope=unsupported",
    "max_num_batched_tokens": "mindie_scope=unsupported",
    "enable_auto_think_choice": "maas_status=开关由 FeatureOverlay 按 model.yaml features 配置渲染,不作 user_cli 直通参数",
    "enable_auto_tool_choice": "maas_status=开关由 FeatureOverlay 按 model.yaml features 配置渲染,不作 user_cli 直通参数",
    "enable_smartqos": "maas_status=开关由 FeatureInject 按引擎类型注入引擎参数,不作 user_cli 直通参数",
    "enable_otlp_traces": "maas_status=开关由 FeatureInject 按引擎类型注入引擎参数,不作 user_cli 直通参数",
    "enable_metrics": "maas_status=开关由 FeatureInject 按引擎类型注入引擎参数,不作 user_cli 直通参数",
    "dtype": "mindie_scope=unsupported",
    "kv_cache_dtype": "mindie_scope=unsupported",
    "quantization_param_path": "mindie_scope=unsupported",
    "block_size": "mindie_scope=unsupported",
    "seed": "mindie_scope=unsupported",
    "enable_chunked_prefill": "mindie_scope=unsupported",
}


def prepare(resolved: ResolvedConfig, request: PipelineRequest) -> MindiePlan:
    """解析并返回唯一一份领域计划；不修改外部文件或公共并行状态。"""
    if resolved.topology == Topology.STANDALONE:
        plan: MindiePlan = resolve_standalone_plan(resolved, request)
    elif resolved.topology == Topology.MULTI_NODE:
        plan = resolve_dual_node_plan(resolved, request)
    else:
        raise NotImplementedError(
            f"MindIE topology {resolved.topology.value!r} is not supported; "
            "only standalone and fixed dual-node are enabled"
        )
    _record_resolution_notes(resolved, plan)
    return plan


def _record_resolution_notes(resolved: ResolvedConfig, plan: MindiePlan) -> None:
    """把关键派生结果写入通用 notes，供 audit 排障但不参与后续计算。"""
    if isinstance(plan, MindieDualNodePlan):
        notes = {
            "mindie_mode": "dual_node",
            "mindie_node_rank": str(plan.node_rank),
            # 日志分析器只消费公共多机事实，不应读取 mindie_node_rank。这里把同一
            # 强类型计划投影到既有 notes 契约，使 rank0 启动分析器、worker 跳过。
            "multi_node_index": str(plan.node_rank),
            "multi_node_role": "head" if plan.node_rank == 0 else "worker",
            "mindie_local_world_size": str(plan.local_world_size),
            "mindie_global_world_size": str(plan.global_world_size),
            "mindie_tp": str(plan.tp),
            "mindie_dp": str(plan.dp),
            "mindie_ranktable_source": str(plan.ranktable.source_path),
            "mindie_ranktable_target": str(plan.ranktable.target_path),
            "mindie_ranktable_device_id_policy": "container_local_ordinal",
        }
    else:
        host_trace = resolved.engine_config_traces.get("host")
        host_source = (
            "placement.rank_ip"
            if host_trace is not None and str(host_trace.final_value) != plan.common.host
            else (host_trace.final_layer if host_trace is not None else "engine_config")
        )
        notes = {
            "mindie_mode": "standalone",
            "mindie_local_world_size": str(plan.local_world_size),
            "mindie_server_host": plan.common.host,
            "mindie_server_host_source": host_source,
        }
    parallel = plan.parallel
    notes.update(
        {
            "mindie_config_template": str(plan.common.config_template_path),
            "mindie_config_target": MINDIE_CONFIG_TARGET_PATH,
            "mindie_is_moe": str(plan.common.model_policy.is_moe).lower(),
            "mindie_ep_enabled": str(parallel.ep_enabled).lower(),
            "mindie_ep_decision_source": ("model_yaml" if parallel.ep_enabled else "model_profile_or_dense_default"),
        }
    )
    for key, value in (
        ("mindie_tp", parallel.tp),
        ("mindie_dp", parallel.dp),
        ("mindie_moe_tp", parallel.moe_tp),
        ("mindie_moe_ep", parallel.moe_ep),
        ("mindie_ep_level", parallel.ep_level),
    ):
        if value is not None:
            notes[key] = str(value)
    # notes 是审计投影，不是第二份领域状态。validator/runtime 始终只消费 plan，避免
    # 字符串化 notes 被误作执行输入后与强类型计划发生漂移。
    resolved.resolution_notes.update(notes)


def _plan_from_resolved(resolved: ResolvedConfig) -> MindiePlan:
    """读取 prepare 结果，并为旧单机直接调用保留无副作用兼容路径。"""
    state = resolved.engine_state
    if isinstance(state, (MindieStandalonePlan, MindieDualNodePlan)):
        return state
    if resolved.topology == Topology.STANDALONE:
        # 历史测试和外部调用可能绕过 Pipeline 直接使用 mindie_adapter。兼容路径没有 request，
        # 因而只使用配置中的 host；标准 Pipeline 才能把 placement.rank_ip 投影为监听地址。
        # 双机必须经过 prepare，不能猜测 placement。
        return resolve_standalone_plan(resolved)
    raise ValueError("MindIE distributed state is missing; resolve through pipeline before validation/rendering")


def validate(resolved: ResolvedConfig) -> ParamValidationResult:
    """验证领域计划存在且配置投影可构造，并返回统一审计结果。"""
    plan = _plan_from_resolved(resolved)
    build_full_config(plan)
    logger.info("MindIE 2.3.0 config validation passed (fail-fast policy)")
    return ParamValidationResult(
        policy="fail_fast",
        supported_params_file="builtin:mindie-2.3.0-project-template",
        status="checked",
        unsupported=[],
    )


def build_launch_plan(resolved: ResolvedConfig) -> EngineLaunchPlan:
    """把已准备计划转换为公共启动计划，并附加 trace 来源注释。"""
    plan = _plan_from_resolved(resolved)
    launch = build_runtime_launch_plan(plan)
    return EngineLaunchPlan(
        argv=launch.argv,
        pre_start_lines=launch.pre_start_lines,
        preview=launch.preview,
        preview_label=launch.preview_label,
        preview_on_new_line=launch.preview_on_new_line,
        repro_trace_lines=build_trace_comment_lines(resolved),
    )


def prepare_control_artifacts(resolved: ResolvedConfig) -> None:
    """Install dual-node inputs owned by wings-control into shared storage."""
    plan = _plan_from_resolved(resolved)
    if isinstance(plan, MindieDualNodePlan):
        prepare_control_ranktable(plan)


def build_trace_comment_lines(resolved: ResolvedConfig) -> list[str]:
    """记录 config 输入终值与来源；注释不参与 repro 执行。"""
    lines = ["# ─── MindIE Engine Config Sources ───"]
    for key, traced in resolved.engine_config_traces.items():
        value = json.dumps(traced.final_value, ensure_ascii=False, default=str)
        lines.append(f"# {key}={value} <- {traced.final_layer} ({traced.source_file} @ {traced.source_path})")
    return lines


MINDIE_EXTENSION = EngineExtension(
    supported_topologies=(Topology.STANDALONE, Topology.MULTI_NODE),
    parameter_translation=ParameterTranslationProfile(
        mapping=_PARAMETER_MAPPING,
        drop_reasons=_DROP_REASONS,
    ),
    post_template_transforms=(device_count_transform,),
    prepare=prepare,
    control_prepare=prepare_control_artifacts,
    validator=validate,
    launch_builder=build_launch_plan,
    health=HealthProfile(
        host_env="MINDIE_HEALTH_HOST",
        port_env="MINDIE_HEALTH_PORT",
        default_host=MINDIE_MANAGEMENT_HOST,
        default_port=MINDIE_MANAGEMENT_PORT,
    ),
    progress=ProgressProfile(
        stage_overrides={
            "model_compiling": {"min": 60, "max": 92, "name": "模型编译"},
            "server_checking": {"min": 92, "max": 98, "name": "服务启动"},
            "ready": {"min": 98, "max": 100, "name": "启动终态"},
        }
    ),
)
