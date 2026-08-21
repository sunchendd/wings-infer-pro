"""PD 规范 topology、rank 与设备分配规划。"""

from __future__ import annotations

import logging
from typing import Dict

from wings_ctl.core.models import (
    ExplicitPdTopology,
    ParallelShape,
    PD_TOPOLOGY_DERIVED_1P1D,
    PD_TOPOLOGY_EXPLICIT_ALLOCATION,
    PdRole,
    PdRuntimeInput,
    ResolvedPdTopology,
)
from wings_ctl.pd.recipe import PdRoleRecipe

logger = logging.getLogger(__name__)


def _validate_capacity(role_tp: int, local_dp: int, device_count: int | None) -> None:
    """校验当前 Pod 的 local ranks 恰好使用 MaaS 分配的全部设备。

    Args:
        role_tp: 当前 role TP。
        local_dp: 当前 Pod local DP 数。
        device_count: MaaS 显式下发卡数。

    Raises:
        ValueError: 卡数缺失，或 ``role_tp * local_dp`` 与卡数不闭合。
    """
    if device_count is None:
        raise ValueError("PD 场景必须显式提供 device_count，供本 Pod 卡组闭合校验。")
    if isinstance(device_count, bool) or not isinstance(device_count, int) or device_count <= 0:
        raise ValueError(f"PD device_count 必须是正整数，当前值为 {device_count!r}。")
    required = role_tp * local_dp
    if required > device_count:
        raise ValueError(
            f"PD 本 Pod 卡数不足：role_tp={role_tp} * dp_size_local={local_dp} "
            f"需要 {required} 卡，device_count={device_count}。"
        )
    if required < device_count:
        raise ValueError(
            f"PD 本 Pod 必须满卡闭合：role_tp={role_tp} * dp_size_local={local_dp} "
            f"仅使用 {required} 卡，device_count={device_count}。"
        )


def _validate_ordinary_device_count(device_count: int | None) -> int:
    """校验普通 PD 的显式卡数并返回唯一 TP。

    Args:
        device_count: MaaS 分配给当前 P 或 D Pod 的卡数。

    Returns:
        普通 PD 按契约使用的 TP。

    Raises:
        ValueError: 卡数缺失、非正整数或不是 2 的幂。
    """
    if device_count is None:
        raise ValueError("普通 PD 必须显式提供 device_count。")
    if isinstance(device_count, bool) or not isinstance(device_count, int) or device_count <= 0:
        raise ValueError(f"普通 PD device_count 必须是正整数，当前值为 {device_count!r}。")
    if device_count & (device_count - 1):
        raise ValueError(f"普通 PD device_count 必须是 2 的幂，当前值为 {device_count}。")
    return device_count


def _resolve_derived_1p1d(
    pd_input: PdRuntimeInput,
    pair: Dict[PdRole, PdRoleRecipe],
    device_count: int | None,
) -> ResolvedPdTopology:
    """解析 strict ordinary 1P1D topology。

    Args:
        pd_input: 当前 Pod 规范输入，六字段必须全缺失。
        pair: P/D exact recipe pair。
        device_count: 当前 Pod 卡数。

    Returns:
        派生 P=0/D=1、DP/local-DP=1 的 topology。

    Raises:
        ValueError: 输入携带六字段、placement 非 singleton，或卡数不是正的 2 次幂。
    """
    if pd_input.explicit_topology is not None:
        raise ValueError("derived_1p1d recipe 不接受 PD topology 六字段。")
    placement = pd_input.placement
    if placement.node_ips is None or len(placement.node_ips) != 1:
        raise ValueError("derived_1p1d 每个 logical Instance 必须恰好一个 Pod。")
    runtime = pair[pd_input.role].runtime
    prefill = runtime.prefill_shape
    decode = runtime.decode_shape
    if prefill.dp_size != 1 or decode.dp_size != 1:
        raise ValueError("derived_1p1d recipe 必须固定 P/D dp_size=1。")
    role_tp = _validate_ordinary_device_count(device_count)
    derived_shape = ParallelShape(dp_size=1, tp_size=role_tp)
    return ResolvedPdTopology(
        input_policy=PD_TOPOLOGY_DERIVED_1P1D,
        role=pd_input.role,
        instance_index=0 if pd_input.role is PdRole.PREFILL else 1,
        prefill=derived_shape,
        decode=derived_shape,
        dp_size_local=1,
        placement=placement,
        member_index=0,
        rank_start=0,
        rank_end_exclusive=1,
    )


def _resolve_explicit_allocation(
    pd_input: PdRuntimeInput,
    explicit: ExplicitPdTopology,
    device_count: int | None,
) -> ResolvedPdTopology:
    """解析 PD 大 EP 的同构 local DP allocation。

    Args:
        pd_input: 当前 Pod 规范输入和 Instance placement。
        explicit: MaaS 原子六字段。
        device_count: 当前 Pod 卡数。

    Returns:
        含 member/rank range 的规范 topology。

    Raises:
        ValueError: role global DP 与 placement closure 不一致，或卡数不闭合。

    ``explicit_allocation`` 的 P/D shape 和成员 Pod 数由 MaaS 规划。exact recipe
    只约束后续 ProcessPlan 使用的静态 engine/connector policy，并提供已验收的推荐
    topology，不限制本次 deployment 的实际 shape。
    """
    placement = pd_input.placement
    assert placement.node_ips is not None
    assert placement.rank_ip is not None
    member_index = placement.node_ips.index(placement.rank_ip)
    role_shape = explicit.prefill if pd_input.role is PdRole.PREFILL else explicit.decode
    expected_global_dp = len(placement.node_ips) * explicit.dp_size_local
    if role_shape.dp_size != expected_global_dp:
        raise ValueError(
            f"PD global DP closure 失败：role={pd_input.role.value} global_dp={role_shape.dp_size}，"
            f"len(NODE_IPS)={len(placement.node_ips)} * DP_SIZE_LOCAL={explicit.dp_size_local} "
            f"应为 {expected_global_dp}。"
        )
    _validate_capacity(role_shape.tp_size, explicit.dp_size_local, device_count)
    rank_start = member_index * explicit.dp_size_local
    return ResolvedPdTopology(
        input_policy=PD_TOPOLOGY_EXPLICIT_ALLOCATION,
        role=pd_input.role,
        instance_index=explicit.pd_index,
        prefill=explicit.prefill,
        decode=explicit.decode,
        dp_size_local=explicit.dp_size_local,
        placement=placement,
        member_index=member_index,
        rank_start=rank_start,
        rank_end_exclusive=rank_start + explicit.dp_size_local,
    )


def resolve_pd_topology(
    pd_input: PdRuntimeInput,
    pair: Dict[PdRole, PdRoleRecipe],
    device_count: int | None,
) -> ResolvedPdTopology:
    """按 exact recipe input policy 规范化当前 Pod PD topology。

    Args:
        pd_input: 当前 Pod 已通过输入契约校验的 PD 输入。
        pair: 已选择且 pair 校验通过的 P/D recipes。
        device_count: 当前 Pod 显式卡数。

    Returns:
        唯一规范 topology。

    Raises:
        ValueError: pair policy 不一致、输入形状不匹配、closure 或容量校验失败。
    """
    runtime = pair[pd_input.role].runtime
    if runtime.topology_input_policy == PD_TOPOLOGY_DERIVED_1P1D:
        resolved = _resolve_derived_1p1d(pd_input, pair, device_count)
    elif runtime.topology_input_policy == PD_TOPOLOGY_EXPLICIT_ALLOCATION:
        if pd_input.explicit_topology is None:
            raise ValueError("explicit_allocation recipe 必须提供完整 PD topology 六字段。")
        resolved = _resolve_explicit_allocation(pd_input, pd_input.explicit_topology, device_count)
    else:  # 固定 schema parser 已拦截；保留边界保护。
        raise ValueError(f"未知 PD topology input policy：{runtime.topology_input_policy!r}。")
    logger.info(
        "PD topology resolved: role=%s instance=%d member=%d ranks=%d..%d",
        resolved.role.value,
        resolved.instance_index,
        resolved.member_index,
        resolved.rank_start,
        resolved.rank_end_exclusive - 1,
    )
    return resolved
