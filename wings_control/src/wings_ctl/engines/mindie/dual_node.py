"""MindIE 2.3.0 固定双节点领域计划。

触发条件仅为已选择 ``MULTI_NODE`` 的 MindIE 请求。部署请求提供当前节点和双节点
规模，固定 ranktable 只作为 MindIE/HCCL 的运行时输入；Wings 仅校验它与已解析
计划一致，不从中反向推导并行值。本模块计算 MindIE 自有的 local/global world size 和并行计划，不调用公共
``coordinate_parallelism()``，也不创建 ``ResolvedNode``。
"""

from __future__ import annotations

from dataclasses import dataclass

from wings_ctl.core.models import PipelineRequest, ResolvedConfig
from wings_ctl.core.topology import Topology
from wings_ctl.engines.mindie.common import (
    MindieCommonSettings,
    MindieParallelPlan,
    build_parallel_plan,
    resolve_common_settings,
)
from wings_ctl.engines.mindie.ranktable import RankTablePlan, resolve_ranktable_paths


DEFAULT_HCCL_MASTER_PORT = 27070


@dataclass(frozen=True)
class MindieDualNodePlan:
    """双机配置与 runtime 使用的已校验事实。

    ``node_rank`` 是当前 Pod 在部署 ``node_ips`` 中的位置，不是 ranktable 内每张
    设备的 rank ID。Control 发布前只核对固定 ranktable 与该计划的一致性，不用
    ranktable 生成第二套拓扑。
    """

    common: MindieCommonSettings
    ranktable: RankTablePlan
    node_ips: tuple[str, ...]
    node_rank: int
    master_ip: str
    local_ip: str
    local_device_ids: tuple[int, ...]
    local_world_size: int
    global_world_size: int
    parallel: MindieParallelPlan
    master_port: int = DEFAULT_HCCL_MASTER_PORT

    @property
    def tp(self) -> int:
        """双机普通 TP 必须存在；属性保留既有调用方的简洁访问方式。"""
        if self.parallel.tp is None:
            raise ValueError("MindIE dual-node parallel plan is missing tp")
        return self.parallel.tp

    @property
    def dp(self) -> int:
        """双机普通 DP 必须存在。"""
        if self.parallel.dp is None:
            raise ValueError("MindIE dual-node parallel plan is missing dp")
        return self.parallel.dp


def resolve_dual_node_plan(resolved: ResolvedConfig, request: PipelineRequest) -> MindieDualNodePlan:
    """以部署 placement 生成双节点计划，不读取 ranktable 或修改外部文件。"""
    if resolved.topology != Topology.MULTI_NODE:
        raise ValueError(f"MindIE dual-node resolver received topology={resolved.topology.value!r}")
    if request.placement is None:
        raise ValueError("MindIE distributed mode requires cluster placement")

    common = resolve_common_settings(resolved)
    placement = request.placement
    node_ips = tuple(str(ip).strip() for ip in (placement.node_ips or []) if str(ip).strip())
    if len(node_ips) != 2:
        raise ValueError(f"MindIE 2.3.0 dual-node mode requires exactly two node_ips; got {len(node_ips)}")
    if len(set(node_ips)) != len(node_ips):
        raise ValueError(f"MindIE 2.3.0 dual-node node_ips must be unique; got {node_ips!r}")
    rank_ip = str(placement.rank_ip or "").strip()
    master_ip = str(placement.master_ip or "").strip()
    if not rank_ip or rank_ip not in node_ips:
        raise ValueError(f"MindIE rank_ip must identify one of node_ips, got {rank_ip!r}")
    if not master_ip or master_ip not in node_ips:
        raise ValueError(f"MindIE master_ip must identify one of node_ips, got {master_ip!r}")
    if master_ip != node_ips[0]:
        raise ValueError(
            "MindIE master_ip must equal node_ips[0] so Wings head and "
            f"ranktable rank-0 server share one identity; got master_ip={master_ip!r}, "
            f"node_ips[0]={node_ips[0]!r}"
        )

    local_count = common.configured_local_device_count
    global_count = len(node_ips) * local_count
    parallel = build_parallel_plan(
        common.model_policy,
        global_count,
        require_tp_dp=True,
    )

    # runtime 会在 Control 阶段校验 ranktable 与本计划的规模一致，并只在共享目标中
    # 把物理 device_id 归一化为容器本地序号；resolve 阶段不读取外部文件。
    return MindieDualNodePlan(
        common=common,
        ranktable=resolve_ranktable_paths(),
        node_ips=node_ips,
        node_rank=node_ips.index(rank_ip),
        master_ip=master_ip,
        local_ip=rank_ip,
        local_device_ids=tuple(range(local_count)),
        local_world_size=local_count,
        global_world_size=global_count,
        parallel=parallel,
    )
