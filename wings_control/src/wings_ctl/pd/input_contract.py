"""PD separation 外部输入解析与本 Pod 可验证约束。"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from wings_ctl.core.models import (
    ClusterPlacement,
    ExplicitPdTopology,
    ParallelShape,
    PdRole,
    PdRuntimeInput,
)

logger = logging.getLogger(__name__)

PD_TOPOLOGY_FIELDS = (
    "PD_INDEX",
    "PD_PREFILL_DP_SIZE",
    "PD_PREFILL_TP_SIZE",
    "PD_DECODE_DP_SIZE",
    "PD_DECODE_TP_SIZE",
    "DP_SIZE_LOCAL",
)


def parse_pd_role(raw_role: str | None) -> tuple[PdRole | None, bool]:
    """解析 ``PD_ROLE``，保留环境变量完全缺失的迁移状态。

    Args:
        raw_role: 环境变量原值；``None`` 表示变量未设置。

    Returns:
        ``(role, missing_legacy_standard)``。标准推理 role 为 ``None``。

    Raises:
        ValueError: 值为空串或不属于 ``none/P/D``。
    """
    if raw_role is None:
        logger.warning("PD_ROLE 未设置，迁移期按标准推理处理；MaaS 应显式下发 PD_ROLE=none")
        return None, True
    if raw_role == "none":
        return None, False
    if raw_role == PdRole.PREFILL.value:
        return PdRole.PREFILL, False
    if raw_role == PdRole.DECODE.value:
        return PdRole.DECODE, False
    raise ValueError(f"PD_ROLE 必须是 'none'、'P' 或 'D'，当前值为 {raw_role!r}；空串也不表示标准推理。")


def _parse_integer_field(env: Mapping[str, str], name: str, *, allow_zero: bool) -> int:
    """解析 PD 原子字段并校验整数值域。

    Args:
        env: 环境变量映射。
        name: 字段名。
        allow_zero: 是否允许零；仅 ``PD_INDEX`` 允许。

    Returns:
        解析后的整数。

    Raises:
        ValueError: 字段为空、不是十进制整数或超出值域。
    """
    raw = env[name]
    if raw == "":
        raise ValueError(f"PD 字段 {name} 不能为空。")
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise ValueError(f"PD 字段 {name} 必须是十进制整数，当前值为 {raw!r}。") from exc
    if allow_zero:
        if value < 0:
            raise ValueError(f"PD 字段 {name} 必须大于等于 0，当前值为 {value}。")
    elif value <= 0:
        raise ValueError(f"PD 字段 {name} 必须是正整数，当前值为 {value}。")
    return value


def parse_explicit_pd_topology(env: Mapping[str, str]) -> ExplicitPdTopology | None:
    """原子解析六个 PD topology 字段。

    Args:
        env: 环境变量映射。

    Returns:
        六字段全缺失时返回 ``None``；全存在时返回规范对象。

    Raises:
        ValueError: 只有部分字段存在，或任一字段值非法。
    """
    present = [name for name in PD_TOPOLOGY_FIELDS if name in env]
    if not present:
        return None
    if len(present) != len(PD_TOPOLOGY_FIELDS):
        missing = [name for name in PD_TOPOLOGY_FIELDS if name not in env]
        raise ValueError(f"PD topology 六字段必须全部存在或全部缺失；已存在={present}，缺失={missing}。")

    return ExplicitPdTopology(
        pd_index=_parse_integer_field(env, "PD_INDEX", allow_zero=True),
        prefill=ParallelShape(
            dp_size=_parse_integer_field(env, "PD_PREFILL_DP_SIZE", allow_zero=False),
            tp_size=_parse_integer_field(env, "PD_PREFILL_TP_SIZE", allow_zero=False),
        ),
        decode=ParallelShape(
            dp_size=_parse_integer_field(env, "PD_DECODE_DP_SIZE", allow_zero=False),
            tp_size=_parse_integer_field(env, "PD_DECODE_TP_SIZE", allow_zero=False),
        ),
        dp_size_local=_parse_integer_field(env, "DP_SIZE_LOCAL", allow_zero=False),
    )


def _normalize_single_pod_placement(placement: ClusterPlacement | None) -> ClusterPlacement:
    """把单 Pod PD Instance 的 placement 归一化为 singleton。

    单 Pod Instance（``--distributed`` 未下发）允许 MaaS 只下发 ``RANK_IP``（当前 Pod
    IP），``MASTER_IP/NODE_IPS`` 可缺省。若部分下发了 ``MASTER_IP``/``NODE_IPS``，其值
    必须与 ``RANK_IP`` 一致（前者 == ``RANK_IP``，后者 == ``[RANK_IP]``），否则视为跨
    Pod 误标、fail-fast。返回值**恒为** ``MASTER_IP=RANK_IP, NODE_IPS=[RANK_IP]`` 的
    singleton，使下游 planner / process-plan 始终拿到合法 placement。

    Args:
        placement: CLI 已解析的运行时 IP 上下文（可能只有 rank_ip，或部分字段）。

    Returns:
        归一化后的 singleton placement（``NODE_IPS=[RANK_IP]``、``MASTER_IP=RANK_IP``）。

    Raises:
        ValueError: 单 Pod Instance 连 ``RANK_IP`` 也缺失，或已下发的
            ``MASTER_IP``/``NODE_IPS`` 与 singleton 不一致。
    """
    if placement is None or not placement.rank_ip:
        raise ValueError("PD 单 Pod Instance 必填 RANK_IP（当前 Pod IP）；MASTER_IP/NODE_IPS 可缺省。")
    if placement.node_ips and placement.node_ips != [placement.rank_ip]:
        raise ValueError(
            "PD 单 Pod Instance 的 NODE_IPS 如存在必须等于 [RANK_IP]；"
            f"NODE_IPS={placement.node_ips!r}，RANK_IP={placement.rank_ip!r}。"
            "多个 Pod 属跨 Pod 场景，应下发 --distributed 并给完整 placement。"
        )
    if placement.master_ip is not None and placement.master_ip != placement.rank_ip:
        raise ValueError(
            "PD 单 Pod Instance 的 MASTER_IP 如存在必须等于 RANK_IP；"
            f"MASTER_IP={placement.master_ip!r}，RANK_IP={placement.rank_ip!r}。"
        )
    return ClusterPlacement(
        rank_ip=placement.rank_ip,
        master_ip=placement.rank_ip,
        node_ips=[placement.rank_ip],
    )


def validate_pd_placement(placement: ClusterPlacement) -> None:
    """校验跨 Pod logical Instance 的完整 placement。

    仅 PD 跨 Pod（``--distributed`` 下发）调用：``--distributed`` 表示当前 logical
    Instance 跨多个 Pod，故要求三字段全存在、``NODE_IPS`` 至少两个成员，并满足
    master-first / IP 唯一 / rank membership。单 Pod Instance 走
    :func:`_normalize_single_pod_placement`，不经过这里的完整校验。

    Args:
        placement: MaaS 下发的 Instance-scoped placement。

    Raises:
        ValueError: placement 缺失、成员少于 2、顺序错误、成员重复或当前 Pod 不在成员中。
    """
    if not placement.master_ip:
        raise ValueError("PD 跨 Pod 场景必填 MASTER_IP，值应为当前 logical Instance 的首个 Pod IP。")
    if not placement.rank_ip:
        raise ValueError("PD 跨 Pod 场景必填 RANK_IP，值应为当前 Pod IP。")
    if not placement.node_ips:
        raise ValueError("PD 跨 Pod 场景必填非空 NODE_IPS，且只包含当前 logical Instance 成员。")
    if len(placement.node_ips) < 2:
        raise ValueError(
            "PD 跨 Pod 场景(--distributed)要求 NODE_IPS 至少 2 个成员；"
            f"当前为单 Pod {placement.node_ips!r}，应走单 Pod 解析而不下发 --distributed。"
        )
    if len(set(placement.node_ips)) != len(placement.node_ips):
        raise ValueError(f"PD NODE_IPS 不允许重复成员，当前值为 {placement.node_ips!r}。")
    if placement.master_ip != placement.node_ips[0]:
        raise ValueError(
            "PD MASTER_IP 必须等于 NODE_IPS[0]；"
            f"MASTER_IP={placement.master_ip!r}，NODE_IPS[0]={placement.node_ips[0]!r}。"
        )
    if placement.node_ips.count(placement.rank_ip) != 1:
        raise ValueError(
            "PD RANK_IP 必须在 NODE_IPS 中恰好出现一次；"
            f"RANK_IP={placement.rank_ip!r}，NODE_IPS={placement.node_ips!r}。"
        )


def parse_pd_runtime_input(
    raw_role: str | None,
    env: Mapping[str, str],
    placement: ClusterPlacement | None,
    *,
    distributed: bool,
) -> tuple[PdRuntimeInput | None, bool]:
    """解析 topology gate 所需的完整 PD 输入。

    ``--distributed`` 只表示“当前 logical Instance 是否跨 Pod”，不是 PD 开关。PD
    单 Pod（``distributed=False``）允许缺 ``MASTER_IP/NODE_IPS``，由 ``RANK_IP`` 派生
    singleton；PD 跨 Pod（``distributed=True``）要求完整 placement 并校验。

    Args:
        raw_role: ``PD_ROLE`` 原始值。
        env: 环境变量映射。
        placement: CLI 已解析的运行时 IP 上下文。
        distributed: 当前 logical Instance 是否跨 Pod（``--distributed``）。

    Returns:
        ``(pd_input, missing_legacy_standard)``；标准推理 ``pd_input=None``。

    Raises:
        ValueError: role、原子字段、distributed 组合或 placement 不满足契约。
    """
    role, missing_legacy_standard = parse_pd_role(raw_role)
    present = [name for name in PD_TOPOLOGY_FIELDS if name in env]
    if role is None:
        if present:
            raise ValueError(f"标准推理不允许残留 PD topology 字段：{present}。")
        return None, missing_legacy_standard

    explicit_topology = parse_explicit_pd_topology(env)

    if distributed:
        if placement is None:
            raise ValueError("PD 跨 Pod 场景(--distributed)必填 MASTER_IP、RANK_IP 和 NODE_IPS。")
        validate_pd_placement(placement)
    else:
        placement = _normalize_single_pod_placement(placement)
    return PdRuntimeInput(role=role, explicit_topology=explicit_topology, placement=placement), False
