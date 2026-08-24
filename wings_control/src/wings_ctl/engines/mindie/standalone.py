"""MindIE 单机领域计划与 device-count 策略。

本模块承接拆包前适配器的单机设备语义：本地卡号始终为从 0 开始的连续逻辑卡，
world size 等于本地卡数。它不读取 ranktable，也不调用公共 TP/DP 算法；服务监听地址
只在通用默认值不可直接用于 MindIE 时，从当前 Pod 的运行时 placement 派生。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from wings_ctl.core.models import PipelineRequest, ResolvedConfig
from wings_ctl.core.topology import Topology
from wings_ctl.engines.mindie.common import (
    MindieCommonSettings,
    MindieParallelPlan,
    build_parallel_plan,
    resolve_common_settings,
)


@dataclass(frozen=True)
class MindieStandalonePlan:
    """单机配置投影需要的已校验事实。"""

    common: MindieCommonSettings
    device_ids: tuple[int, ...]
    local_world_size: int
    parallel: MindieParallelPlan


def device_count_transform(engine_config: dict, ctx: dict[str, Any]) -> tuple[dict, dict]:
    """把 MaaS 本地卡数写入 MindIE 平面 trace，不推导公共 TP/DP。"""
    device_count = ctx.get("device_count")
    if device_count is None:
        return {}, {}
    if isinstance(device_count, bool) or not isinstance(device_count, int) or device_count <= 0:
        raise ValueError(f"MindIE device-count must be a positive integer, got {device_count!r}")
    return (
        {"local_device_count": device_count},
        {
            "mindie_local_device_count": str(device_count),
            "mindie_device_count_status": "applied",
        },
    )


def _apply_runtime_bind_host(
    resolved: ResolvedConfig,
    request: PipelineRequest | None,
    common: MindieCommonSettings,
) -> MindieCommonSettings:
    """用当前 Pod 的 ``RANK_IP`` 收敛 MindIE 默认监听地址。

    通用层的 ``0.0.0.0`` 默认值适合允许 wildcard bind 的引擎，但 MindIE 2.3.0 模板将
    ``allowAllZeroIpListening`` 固定为 ``false``。因此，只有 host 仍来自最低优先级默认层时，
    才使用部署注入的 ``placement.rank_ip``；模型配置或用户显式 ``--host`` 始终优先。

    兼容直接调用 adapter 的旧入口时没有 request，此处保留原值，不读取环境变量，避免领域
    resolver 产生隐藏输入。标准 Pipeline 会显式传入 placement 并完成 Pod IP 投影。
    """
    host_trace = resolved.engine_config_traces.get("host")
    if common.host != "0.0.0.0":
        return common
    if host_trace is not None and host_trace.final_layer != "builtin_default":
        return common
    if request is None:
        # 迁移期兼容入口没有 PipelineRequest；标准 Pipeline 必须走下面的强校验。
        return common
    rank_ip = (request.placement.rank_ip or "").strip() if request.placement is not None else ""
    if not rank_ip:
        raise ValueError("MindIE standalone requires RANK_IP or an explicit host because allowAllZeroIpListening=false")
    return replace(common, host=rank_ip)


def resolve_standalone_plan(
    resolved: ResolvedConfig,
    request: PipelineRequest | None = None,
) -> MindieStandalonePlan:
    """生成单机计划；其它 topology 明确拒绝，防止误用单机设备布局。"""
    if resolved.topology != Topology.STANDALONE:
        raise ValueError(f"MindIE standalone resolver received topology={resolved.topology.value!r}")
    common = _apply_runtime_bind_host(
        resolved,
        request,
        resolve_common_settings(resolved),
    )
    count = common.configured_local_device_count
    return MindieStandalonePlan(
        common=common,
        device_ids=tuple(range(count)),
        local_world_size=count,
        parallel=build_parallel_plan(
            common.model_policy,
            count,
            require_tp_dp=False,
        ),
    )
