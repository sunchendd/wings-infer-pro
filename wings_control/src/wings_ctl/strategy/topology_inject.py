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

from wings_ctl.strategy.parallelism import dp_local_from_device_count, dp_start_rank

logger = logging.getLogger(__name__)

# nic 探测:默认路由网卡(复用旧 wings-control)。只读 /proc/net/route,容器内无需特权;
# 无默认路由兜底 eth0。运行时在本 Pod 的 shell 执行。
NIC_DETECT_CMD = "$(awk '$2==\"00000000\"{print $1;exit}' /proc/net/route 2>/dev/null || echo eth0)"


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
            f"NODE_IPS 长度({len(node_ips)})与 recipe nodes[] 条数({node_count})不一致:"
            "集群规模须与配方一致"
        )
    if rank_ip not in node_ips:
        raise ValueError(
            f"RANK_IP={rank_ip} 不在 NODE_IPS={node_ips} 中:无法确定本 Pod 节点身份"
        )
    # 无 MASTER_IP 无法确定 head(node_specs[0] 恒为 head,须有对应 IP)。
    if master_ip is None:
        raise ValueError(
            f"multi_node 缺 MASTER_IP:无法确定 head 节点(NODE_IPS={node_ips})"
        )
    # master 必须是 NODE_IPS 首位,否则 index↔node_spec 映射失配(master Pod 会拿到 worker 配置)。
    if node_ips[0] != master_ip:
        raise ValueError(
            f"MASTER_IP={master_ip} 必须为 NODE_IPS 首位(当前 NODE_IPS={node_ips});"
            "否则 master Pod 会被映射到 worker 配置(node_rank≠0/headless),静默错配。"
            "请确认 MaaS 下发的 NODE_IPS 以 master 打头。"
        )
    index = node_ips.index(rank_ip)
    role = "head" if rank_ip == master_ip else "worker"  # 不变量下等价于 index == 0
    logger.info(
        "multi_node 选节点:rank_ip=%s index=%d role=%s (node_ips=%s, master=%s)",
        rank_ip, index, role, node_ips, master_ip,
    )
    return NodeSelection(index=index, role=role)


# ── 维护说明:coordinate_parallelism 多机并行布局概览 ─────────────────────────────
# 职责:按 layout 算并注入 DP 相关 engine_config;不支持/危险组合直接 fail-fast(宁可报错不静默错配)。
#       TP、PP 一律沿用模板,本函数只协调 DP;不渲染 argv、不读 YAML(那是 adapter / loaders 的事)。
# 两类 layout(detect_layout 按 per-Pod 身份键判,见 _LAYOUT_KEYS):
#   DP_across:TP 在单 Pod 内、DP 跨 Pod。每 Pod 放 dp_local = device_count // TP → DP = pod_count × dp_local。
#   TP_across:一个 TP 组跨多个 Pod。world_size = pod_count × device_count → DP = world_size // TP。
# fail-fast:非整除(不向下取整)、pipeline_parallel_size>1、TP 跨且算出 DP>1(node_rank 摆放未确认)。
# 未下发 device_count → 不协调,返回空覆盖层(沿用模板)。
def coordinate_parallelism(
    template_engine_config: dict,
    *,
    device_count: int | None,
    pod_count: int,
    index: int,
) -> tuple[dict, dict]:
    """根据 ``device_count`` 计算多机场景下的 DP 覆盖参数。

    **TP / PP 一律沿用模板**;这里仅协调 DP。记 ``world_size = pod_count × device_count``。
    计算分两种布局:

    - **DP_across**(含 ``data_parallel_start_rank`` / ``data_parallel_size_local``,TP 在 Pod 内):
      每 Pod 放 ``dp_local = cnt // TP`` 份 → ``DP = pod_count × dp_local``、``start_rank = index × dp_local``。
      前提 ``cnt ≥ TP`` 且 ``cnt % TP == 0``,否则 raise(不向下取整)。
    - **TP_across**(含 ``node_rank``):``DP = world_size // TP``;前提 ``world_size % TP == 0``
      否则 raise;算出 ``DP > 1``(多 TP 组)→ raise 暂不支持(node_rank 摆放未确认)。

    ``pipeline_parallel_size > 1`` 时直接报错(当前未支持)。
    未传 ``device_count`` 时返回空覆盖层,沿用模板参数。

    Args:
        template_engine_config: 选中节点的模板 engine_config(只读)。
        device_count: 本 Pod 卡数(None=不协调)。
        pod_count: 集群 Pod 数(= len(NODE_IPS))。
        index: 本 Pod 下标(决定 start_rank)。

    Returns:
        ``(override_layer, notes)``:计算出的覆盖层与摘要信息。

    Raises:
        ValueError: 当前输入不满足约束(如非整除、PP>1、卡数非法等)。
    """
    pp = template_engine_config.get("pipeline_parallel_size") or 1
    if pp > 1:
        raise ValueError(
            f"pipeline_parallel_size={pp}>1:PP 暂不支持(tp_pp 策略不应被选中)"
        )
    if device_count is None:
        # 未下发 device_count → 不协调;但 DP_across 仍要检查模板 DP 与集群规模是否一致,
        # 避免 start_rank 越界。
        if detect_layout(template_engine_config) == LAYOUT_DP_ACROSS:
            dp = template_engine_config.get("data_parallel_size")
            dp_local = template_engine_config.get("data_parallel_size_local")
            if dp is not None and dp_local and dp != pod_count * dp_local:
                raise ValueError(
                    f"DP 配置与集群规模不一致:data_parallel_size={dp} ≠ "
                    f"pod_count({pod_count})×data_parallel_size_local({dp_local});"
                    "未下发 --device-count 时不自动改 DP,请确认 NODE_IPS 数量与配方一致"
                    "(或下发 --device-count 由策略层协调)。"
                )
        return {}, {}
    if device_count <= 0:
        raise ValueError(f"device-count={device_count} 非法(须为正整数)")

    tp = template_engine_config.get("tensor_parallel_size") or 1
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
        # TP_across
        if world_size % tp != 0:
            raise ValueError(
                f"world_size={world_size} 不是 tensor_parallel_size={tp} 的整数倍:不支持(不向下取整)"
            )
        dp = world_size // tp
        if dp > 1:
            raise ValueError(
                f"TP 跨 Pod 且算出 DP={dp}>1(多 TP 组):暂不支持(node_rank 摆放未确认)"
            )
        tpl_dp = template_engine_config.get("data_parallel_size") or 1
        notes["multinode_dp_resolved_dp"] = str(dp)
        if dp == tpl_dp:
            notes["multinode_dp_status"] = "noop"
            logger.info("multi_node 协调(TP 跨):DP=%d(=模板),world_size=%d TP=%d", dp, world_size, tp)
            return {}, notes
        notes["multinode_dp_status"] = "overridden"
        logger.info("multi_node 协调(TP 跨):DP %d→%d,world_size=%d TP=%d", tpl_dp, dp, world_size, tp)
        return {"data_parallel_size": dp}, notes

    # DP_across。DP-local 与 start_rank 复用公共函数。
    dp_local = dp_local_from_device_count(device_count, tp)
    dp = pod_count * dp_local
    start_rank = dp_start_rank(index, dp_local)
    notes.update({
        "multinode_dp_resolved_dp": str(dp),
        "multinode_dp_size_local": str(dp_local),
        "multinode_dp_start_rank": str(start_rank),
    })
    tpl_dp = template_engine_config.get("data_parallel_size") or 1
    tpl_local = template_engine_config.get("data_parallel_size_local") or 1
    tpl_sr = template_engine_config.get("data_parallel_start_rank") or 0
    if dp == tpl_dp and dp_local == tpl_local and start_rank == tpl_sr:
        notes["multinode_dp_status"] = "noop"
        logger.info("multi_node 协调(DP 跨):DP=%d dp_local=%d start_rank=%d(=模板)", dp, dp_local, start_rank)
        return {}, notes
    notes["multinode_dp_status"] = "overridden"
    logger.info(
        "multi_node 协调(DP 跨):DP=%d dp_local=%d start_rank=%d(index=%d,pod_count=%d,cnt=%d,TP=%d)",
        dp, dp_local, start_rank, index, pod_count, device_count, tp,
    )
    return (
        {
            "data_parallel_size": dp,
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
    "$HEAD_IP": ("master_ip", "literal"),   # nvidia,与 $node0_ip 同源(=MASTER_IP)
    "$nic_name": ("nic", "runtime"),
    "$IFACE_NAME": ("nic", "runtime"),       # nvidia,与 $nic_name 同处理
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
    runtime 类型(`$nic_name`/`$IFACE_NAME`)不在这里处理。

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


def runtime_var_commands(*value_dicts: dict) -> list[str]:
    """扫描 runtime 占位符,生成对应的 inline 探测命令。

    返回例如 ``["nic_name=$(...)"]`` 或 ``["IFACE_NAME=$(...)"]``。
    这些命令需在 env export 之前执行,否则后续变量引用无法展开。

    Args:
        *value_dicts: 待扫描的值 dict(engine_config / env)。

    Returns:
        inline 命令列表(每个 runtime 占位一条);无则空。
    """
    runtime_tokens = [tok for tok, (_src, kind) in _PLACEHOLDERS.items() if kind == "runtime"]
    cmds: list[str] = []
    for tok in runtime_tokens:
        found = False
        for value_dict in value_dicts:
            for _key, value in value_dict.items():
                if isinstance(value, str) and tok in value:
                    found = True
                    break
            if found:
                break
        if found:
            cmds.append(f"{tok[1:]}={NIC_DETECT_CMD}")  # tok[1:] = 去掉前导 $
    return cmds
