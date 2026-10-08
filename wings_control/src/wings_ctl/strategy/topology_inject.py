"""multi_node 运行时注入逻辑。

本模块只做三件事:
1. 根据运行时 IP 选择当前 Pod 对应的节点配置;
2. 计算多机下需要覆盖的并行参数;
3. 处理运行时占位符。

模块返回的都是纯数据(override、notes、命令行片段),不直接写文件。
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from wings_ctl.engines.delivery_contract import (
    build_parallelism_override,
    get_engine_delivery_contract,
    read_parallelism_values,
)
from wings_ctl.strategy.parallelism import dp_local_from_device_count, dp_start_rank

logger = logging.getLogger(__name__)

# 多机布局标签:
# - DP_across: TP 在单 Pod 内,DP 跨 Pod
# - TP_across: 一个 TP 组跨多个 Pod
LAYOUT_DP_ACROSS = "DP_across"
LAYOUT_TP_ACROSS = "TP_across"

# per-Pod 身份键 → 布局标签。命中即定;没命中默认走 DP_across。
_LAYOUT_KEYS: dict[str, str] = {"node_rank": LAYOUT_TP_ACROSS}

# coordinate_parallelism 写进 notes 的 strategy status —— "multinode_dp_status" 取值全集
# (会出现在 audit / resolution_notes,排查多机 DP 时对照):
#   - "noop"       : 按 device_count × pod_count 算出的多机 DP == 模板值,不覆盖(仅记录)。
#   - "overridden" : 算出的 DP(及 DP_across 的 start_rank/dp_local)改了模板,写覆盖层。
# 未下发 device_count 时不写 status(返回空覆盖层,沿用模板)。


def detect_layout(engine_config: dict) -> str:
    """根据 per-Pod 身份键判断多机布局。

    Args:
        engine_config: 节点模板 engine_config(只读);按其含 ``node_rank`` 等键判布局。

    Returns:
        ``LAYOUT_TP_ACROSS``(含 ``node_rank``)或 ``LAYOUT_DP_ACROSS``(其余,默认 DP 跨)。
    """
    for key, layout in _LAYOUT_KEYS.items():
        if key in engine_config:
            return layout
    return LAYOUT_DP_ACROSS


class NodeSelection(NamedTuple):
    """本 Pod 选中的节点身份。

    Attributes:
        index: 本 Pod 在 NODE_IPS / nodes[] 中的下标(0 = head)。
        role: ``head``(RANK_IP == MASTER_IP)否则 ``worker``。
    """
    index: int
    role: str


def select_node(
    node_count: int,
    *,
    rank_ip: str,
    node_ips: list[str],
    master_ip: str | None,
) -> NodeSelection:
    """根据运行时 IP 选出当前 Pod 的节点下标与角色。

    规则:NODE_IPS 首个必须是 master;``index = NODE_IPS.index(RANK_IP)``;
    ``role = head iff RANK_IP == MASTER_IP``(即 index 0),否则 worker。
    输入不一致时直接报错,避免把错误配置继续传到后续流程。

    **关键前提**:``node_specs[k]`` 与 ``NODE_IPS[k]`` 按下标一一对应,
    且 ``node_specs[0]`` 恒为 head。故必须 ``MASTER_IP`` 存在且 ``== NODE_IPS[0]``,否则
    master Pod 会被映射到 worker 配置,形成静默错配。

    Args:
        node_count: recipe nodes[] 的条数(集群规模)。
        rank_ip: 本 Pod IP。
        node_ips: 全集群 IP 列表(已按序解析)。
        master_ip: master IP;用于判定 head,且须为 NODE_IPS 首位。

    Returns:
        NodeSelection(index, role)。

    Raises:
        ValueError: 运行时 IP 信息不合法,或和 recipe 规模不一致。
    """
    if len(node_ips) != node_count:
        raise ValueError(
            f"NODE_IPS length ({len(node_ips)}) does not match recipe nodes[] length ({node_count}); "
            "cluster size must match the recipe"
        )
    if rank_ip not in node_ips:
        raise ValueError(
            f"RANK_IP={rank_ip} is not in NODE_IPS={node_ips}; cannot determine the current Pod identity"
        )
    # 无 MASTER_IP 无法确定 head(node_specs[0] 恒为 head,须有对应 IP)。
    if master_ip is None:
        raise ValueError(
            f"multi_node is missing MASTER_IP; cannot determine the head node (NODE_IPS={node_ips})"
        )
    # master 必须是 NODE_IPS 首位,否则 index↔node_spec 映射失配(master Pod 会拿到 worker 配置)。
    if node_ips[0] != master_ip:
        raise ValueError(
            f"MASTER_IP={master_ip} must be the first NODE_IPS entry (NODE_IPS={node_ips}); "
            "otherwise the master Pod could be mapped to worker configuration. "
            "Ensure MaaS sends NODE_IPS with the master first."
        )
    index = node_ips.index(rank_ip)
    role = "head" if rank_ip == master_ip else "worker"  # 不变量下等价于 index == 0
    logger.info(
        "multi_node selected node: rank_ip=%s index=%d role=%s (node_ips=%s, master=%s)",
        rank_ip, index, role, node_ips, master_ip,
    )
    return NodeSelection(index=index, role=role)


# ── 维护说明:coordinate_parallelism 多机并行布局概览 ─────────────────────────────
# 职责:按 layout 计算并注入多机并行参数;不支持/危险组合直接 fail-fast(宁可报错不静默错配)。
#       DP_across 保持模板 TP,协调每 Pod 的 DP-local、集群 DP 与 start-rank;
#       TP_across 将 world_size 视为同一 TP 组的实际卡数,必要时按单机规则收缩 TP。
#       不渲染 argv、不读 YAML(那是 adapter / loaders 的事)。
# 两类 layout(detect_layout 按 per-Pod 身份键判,见 _LAYOUT_KEYS):
#   DP_across:TP 在单 Pod 内、DP 跨 Pod。dp_local = device_count // TP，
#              DP = pod_count × dp_local，start-rank = index × dp_local。
#   TP_across:所有 Pod 的卡共同组成一份模型的 TP 组，world_size = pod_count × device_count。
#              world_size < TP 时按单机收缩规则得到 TP=world_size、DP=1；
#              world_size >= TP 时要求整除，DP>1 的多 TP 组暂不支持。
# fail-fast:非法卡数、pipeline_parallel_size>1、DP_across 卡数不足或非 TP 整数倍、
#   TP_across 收缩卡数非 2 的幂、world_size 非 TP 整数倍、或算出多个 TP 组。
# 未下发 device_count → 不协调,返回空覆盖层(沿用模板;DP_across 仍做静态一致性检查)。
def coordinate_parallelism(
    template_engine_config: dict,
    *,
    engine: str = "vllm",
    device_count: int | None,
    pod_count: int,
    index: int,
) -> tuple[dict, dict]:
    """根据每 Pod 卡数计算多机场景下的 TP/DP 覆盖参数。

    记 ``world_size = pod_count × device_count``。布局由 ``detect_layout`` 判定:

    - **DP_across**(含 ``data_parallel_start_rank`` / ``data_parallel_size_local``,TP 在 Pod 内):
      每 Pod 放 ``dp_local = cnt // TP`` 份 → ``DP = pod_count × dp_local``、``start_rank = index × dp_local``。
      前提 ``cnt ≥ TP`` 且 ``cnt % TP == 0``,否则 raise(不向下取整)。
    - **TP_across**(含 ``node_rank``):先校验 ``world_size`` 为 2 的幂，
      然后始终使用全部实际卡作为 TP，DP 保持模板值。

    ``pipeline_parallel_size > 1`` 时直接报错(当前未支持)。
    未传 ``device_count`` 时返回空覆盖层,沿用模板参数。

    Args:
        template_engine_config: 选中节点的模板 engine_config(只读)。
        device_count: 每个 Pod 的实际卡数(None=不协调)。TP_across 会先计算 world_size。
        pod_count: 集群 Pod 数(= len(NODE_IPS))。
        index: 本 Pod 下标(决定 start_rank)。

    Returns:
        ``(override_layer, notes)``:计算出的覆盖层与摘要信息。

    Raises:
        ValueError: 当前输入不满足硬约束(如 TP 收缩非 2 的幂、非整除、PP>1、卡数非法等)。
    """
    tp, template_dp, pp = read_parallelism_values(template_engine_config, engine=engine)
    if pp > 1:
        raise ValueError(
            f"pipeline_parallel_size={pp}>1: pipeline parallelism is not supported"
        )
    if device_count is None:
        # 未下发 device_count → 不协调;但 DP_across 仍要检查模板 DP 与集群规模是否一致,
        # 避免 start_rank 越界。
        if detect_layout(template_engine_config) == LAYOUT_DP_ACROSS:
            _, dp, _ = read_parallelism_values(template_engine_config, engine=engine)
            dp_local = template_engine_config.get("data_parallel_size_local")
            if dp is not None and dp_local and dp != pod_count * dp_local:
                raise ValueError(
                    f"DP configuration does not match cluster size: data_parallel_size={dp} != "
                    f"pod_count({pod_count}) × data_parallel_size_local({dp_local}); "
                    "without --device-count, DP is not adjusted automatically. Verify NODE_IPS and recipe size."
                )
        return {}, {}
    if device_count <= 0:
        raise ValueError(f"device-count={device_count} is invalid; it must be a positive integer")

    world_size = pod_count * device_count
    layout = detect_layout(template_engine_config)
    notes = {
        "multinode_dp_tp": str(tp),
        "multinode_dp_pod_count": str(pod_count),
        "multinode_dp_device_count": str(device_count),
        "multinode_dp_world_size": str(world_size),
        "multinode_dp_layout": layout,
    }

    if layout == LAYOUT_TP_ACROSS:
        # TP_across 先校验 world_size，再使用全部实际卡作为 TP；DP 始终沿用模板值。
        if world_size & (world_size - 1):
            raise ValueError(f"world_size={world_size} is not a power of two")

        tpl_dp = template_dp
        resolved_tp = world_size
        notes.update({
            "multinode_dp_resolved_tp": str(resolved_tp),
            "multinode_dp_resolved_dp": str(tpl_dp),
            "multinode_dp_status": "warning_tp_overridden" if resolved_tp != tp else "noop",
        })
        if resolved_tp != tp:
            logger.warning(
                "multi_node runtime values differ from the TP-across template: template TP=%d, DP=%d; "
                "world_size=%d, setting TP=%d while keeping DP=%d",
                tp, tpl_dp, world_size, resolved_tp, tpl_dp,
            )
            return build_parallelism_override(engine=engine, tp=resolved_tp), notes
        logger.info(
            "multi_node coordination (TP-across): TP=%d (=world_size), keeping DP=%d, world_size=%d",
            resolved_tp, tpl_dp, world_size,
        )
        return {}, notes

    # DP_across。DP-local 与 start_rank 复用公共函数。
    dp_local = dp_local_from_device_count(device_count, tp)
    dp = pod_count * dp_local
    start_rank = dp_start_rank(index, dp_local)
    notes.update({
        "multinode_dp_resolved_dp": str(dp),
        "multinode_dp_size_local": str(dp_local),
        "multinode_dp_start_rank": str(start_rank),
    })
    tpl_dp = template_dp
    tpl_local = template_engine_config.get("data_parallel_size_local") or 1
    tpl_sr = template_engine_config.get("data_parallel_start_rank") or 0
    if dp == tpl_dp and dp_local == tpl_local and start_rank == tpl_sr:
        notes["multinode_dp_status"] = "noop"
        logger.info(
            "multi_node coordination (DP-across): DP=%d dp_local=%d start_rank=%d (matches template)",
            dp, dp_local, start_rank,
        )
        return {}, notes
    notes["multinode_dp_status"] = "overridden"
    logger.info(
        "multi_node coordination (DP-across): DP=%d dp_local=%d start_rank=%d "
        "(index=%d, pod_count=%d, count=%d, TP=%d)",
        dp, dp_local, start_rank, index, pod_count, device_count, tp,
    )
    return (
        {
            **build_parallelism_override(engine=engine, dp=dp),
            "data_parallel_size_local": dp_local,
            "data_parallel_start_rank": start_rank,
        },
        notes,
    )


# 占位符注册表: token -> (来源, 类型)
# - literal: 解析阶段可确定,直接替换
# - runtime: 需运行时探测(如网卡名),通过 inline 命令赋值
_PLACEHOLDERS: dict[str, tuple[str, str]] = {
    "$local_ip": ("rank_ip", "literal"),
    "$node0_ip": ("master_ip", "literal"),
    "$HEAD_IP": ("master_ip", "literal"),
    "${HEAD_IP}": ("master_ip", "literal"),
}


def _literal_placeholder_value(src: str, *, rank_ip: str, master_ip: str | None) -> str:
    """literal 占位符按其"来源"取真实 IP。

    ``_PLACEHOLDERS`` 里 literal 占位的 src 只有两种:
    - ``rank_ip`` 源(如 ``$local_ip``)→ 本 Pod IP;
    - ``master_ip`` 源(如 ``$node0_ip`` / ``$HEAD_IP``)→ master IP;**缺 master_ip 时退回 rank_ip**
      (单机/降级下不产出空值,与旧逻辑一致)。
    """
    if src == "rank_ip":
        return rank_ip
    # 其余 literal 源即 master_ip:有 master_ip 用之,否则退回 rank_ip。
    return master_ip if master_ip is not None else rank_ip


def substitute_literal_placeholders(
    values: dict,
    *,
    rank_ip: str,
    master_ip: str | None,
) -> dict:
    """替换 literal 类型占位符并返回覆盖层。

    只返回发生变化的键;未变化的键不出现在返回值里。

    Args:
        values: engine_config 或 env 的模板 dict(只读)。
        rank_ip: 本 Pod IP(填 rank_ip 来源的占位)。
        master_ip: master IP(填 master_ip 来源的占位;缺省退回 rank_ip)。

    Returns:
        override dict:``{key: 替换后的值}``,仅含值里出现过 literal 占位的键。
    """
    # 每个 literal 占位符 → 真实 IP(取值逻辑见 _literal_placeholder_value;拆掉旧的嵌套三元)。
    subst = {
        tok: _literal_placeholder_value(src, rank_ip=rank_ip, master_ip=master_ip)
        for tok, (src, kind) in _PLACEHOLDERS.items()
        if kind == "literal"
    }
    override: dict = {}
    for k, v in values.items():
        if not isinstance(v, str):
            continue
        nv = v
        for tok, real in subst.items():
            nv = nv.replace(tok, real)
        if nv != v:
            override[k] = nv
    return override


def build_data_parallel_address_override(
    engine_config: dict,
    *,
    master_ip: str | None,
) -> dict:
    """按 recipe 参数声明生成普通多机 DP 协调地址覆盖。

    recipe 中的值只声明参数形态，最终地址由当前 runtime placement 独占。
    未声明该参数时不为引擎扩展新参数。

    Args:
        engine_config: 当前选中节点的 recipe 参数。
        master_ip: 当前 engine instance 的 master IP。

    Returns:
        包含 runtime ``data_parallel_address`` 的覆盖层，或空字典。

    Raises:
        ValueError: recipe 声明该参数但 runtime placement 缺少 ``MASTER_IP``。
    """
    if "data_parallel_address" not in engine_config:
        return {}
    if not master_ip:
        raise ValueError(
            "multi_node recipe declares data_parallel_address but runtime placement is missing MASTER_IP"
        )
    return {"data_parallel_address": master_ip}


def validate_recipe_rendezvous_address(
    engine_config: dict,
    *,
    engine: str,
) -> int | None:
    """校验契约声明的 recipe rendezvous 地址并返回端口。"""
    param = get_engine_delivery_contract(engine).rendezvous_address_param
    if param is None:
        return None

    recipe_value = engine_config.get(param)
    if not isinstance(recipe_value, str):
        raise ValueError(f"engine={engine!r} multi_node recipe requires string {param!r}; received {recipe_value!r}.")
    host, separator, port_text = recipe_value.strip().rpartition(":")
    if not separator or not host or not port_text.isdecimal():
        raise ValueError(f"engine={engine!r} multi_node {param!r} must use 'host:port'; received {recipe_value!r}.")

    port = int(port_text)
    if not 1 <= port <= 65535:
        raise ValueError(f"engine={engine!r} multi_node {param!r} port must be in 1..65535; received {recipe_value!r}.")
    return port


def build_rendezvous_address_override(
    engine_config: dict,
    *,
    engine: str,
    master_ip: str,
) -> dict:
    """使用运行时 master IP 重建契约声明的 rendezvous 地址。

    recipe 中的地址仅提供 rendezvous 端口；实际 head 地址必须来自本次
    placement。未声明该参数的引擎不产生覆盖层。
    """
    param = get_engine_delivery_contract(engine).rendezvous_address_param
    if param is None:
        return {}
    port = validate_recipe_rendezvous_address(engine_config, engine=engine)
    if port is None:
        raise ValueError(f"multi_node rendezvous override requires a valid recipe {param} port")
    recipe_value = engine_config[param]
    resolved = f"{master_ip}:{port}"
    logger.info(
        "multi_node rendezvous override: %s=%s (recipe=%s)",
        param,
        resolved,
        recipe_value,
    )
    return {param: resolved}
