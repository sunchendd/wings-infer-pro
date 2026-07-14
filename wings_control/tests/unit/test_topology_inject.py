"""TopologyRuntimeInject 纯逻辑单测(docs/32):选 node / R-G v3 协调 / 占位填充。"""

from __future__ import annotations

import pytest

from wings_ctl.strategy.topology_inject import (
    LAYOUT_DP_ACROSS,
    LAYOUT_TP_ACROSS,
    NIC_DETECT_CMD,
    coordinate_parallelism,
    detect_layout,
    runtime_var_commands,
    select_node,
    substitute_literal_placeholders,
)


# ─── detect_layout(单一布局判定点:键 → 布局)──────────────────────────────

def test_detect_layout_tp_across_by_node_rank():
    """验证含 node_rank → B 类 TP 跨 Pod。"""
    assert detect_layout({"tensor_parallel_size": 8, "node_rank": 0}) == LAYOUT_TP_ACROSS


def test_detect_layout_dp_across_default():
    """验证无 node_rank(含 data_parallel_start_rank 或纯 TP)→ A 类 DP 跨(默认)。"""
    assert detect_layout({"data_parallel_start_rank": 0}) == LAYOUT_DP_ACROSS
    assert detect_layout({"tensor_parallel_size": 8}) == LAYOUT_DP_ACROSS


# ─── select_node ───────────────────────────────────────────────────────────

def test_select_node_head_when_rank_is_master():
    """验证 RANK_IP == MASTER_IP 时选中 index 0 且 role=head。"""
    sel = select_node(2, rank_ip="10.0.0.1", node_ips=["10.0.0.1", "10.0.0.2"], master_ip="10.0.0.1")
    assert sel.index == 0 and sel.role == "head"


def test_select_node_worker_by_position():
    """验证 worker 的 index = 本 Pod IP 在 NODE_IPS 中的下标,role=worker。"""
    sel = select_node(2, rank_ip="10.0.0.2", node_ips=["10.0.0.1", "10.0.0.2"], master_ip="10.0.0.1")
    assert sel.index == 1 and sel.role == "worker"


def test_select_node_p4_supported():
    """验证 P=4(GLM-5)选 node 正常,不写死 P=2。"""
    ips = ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"]
    sel = select_node(4, rank_ip="10.0.0.3", node_ips=ips, master_ip="10.0.0.1")
    assert sel.index == 2 and sel.role == "worker"


def test_select_node_raises_when_rank_not_in_node_ips():
    """验证 RANK_IP 不在 NODE_IPS 时强校验 raise。"""
    with pytest.raises(ValueError, match="不在 NODE_IPS"):
        select_node(2, rank_ip="10.9.9.9", node_ips=["10.0.0.1", "10.0.0.2"], master_ip="10.0.0.1")


def test_select_node_raises_when_length_mismatch():
    """验证集群规模与 recipe 条数不一致时 raise。"""
    with pytest.raises(ValueError, match="不一致"):
        select_node(3, rank_ip="10.0.0.1", node_ips=["10.0.0.1", "10.0.0.2"], master_ip="10.0.0.1")


def test_select_node_raises_when_master_not_first():
    """D1 修复:MASTER_IP 非 NODE_IPS 首位 → raise(否则 master Pod 拿 worker 配置,静默错配)。"""
    with pytest.raises(ValueError, match="首位"):
        select_node(2, rank_ip="10.0.0.1", node_ips=["10.0.0.2", "10.0.0.1"], master_ip="10.0.0.1")


def test_select_node_raises_when_master_missing():
    """D2 修复:缺 MASTER_IP → raise(node_specs[0] 恒为 head,须有对应 IP)。"""
    with pytest.raises(ValueError, match="MASTER_IP"):
        select_node(2, rank_ip="10.0.0.1", node_ips=["10.0.0.1", "10.0.0.2"], master_ip=None)


# ─── coordinate_parallelism · A 类(DP 跨 Pod,含 data_parallel_start_rank)──────

_A = {"tensor_parallel_size": 8, "data_parallel_size": 2,
      "data_parallel_size_local": 1, "data_parallel_start_rank": 0}


def test_coord_none_device_count_noop():
    """验证未传 device_count → 不协调,空 override。"""
    assert coordinate_parallelism(_A, device_count=None, pod_count=2, index=0) == ({}, {})


def test_coord_a_noop_when_matches_template():
    """验证 A 类 cnt=8(=模板隐含)→ no-op,DP=2。"""
    override, notes = coordinate_parallelism(_A, device_count=8, pod_count=2, index=0)
    assert not override
    assert notes["multinode_dp_status"] == "noop"
    assert notes["multinode_dp_layout"] == "DP_across" and notes["multinode_dp_resolved_dp"] == "2"


def test_coord_a_scales_dp_and_couples():
    """验证 A 类加卡:DP=P×(cnt//TP),联动 dp_local/start_rank(worker index=1,cnt=16)。"""
    override, notes = coordinate_parallelism(_A, device_count=16, pod_count=2, index=1)
    assert override == {
        "data_parallel_size": 4,           # 2 × (16//8)
        "data_parallel_size_local": 2,     # 16//8
        "data_parallel_start_rank": 2,     # index 1 × dp_local 2
    }
    assert notes["multinode_dp_status"] == "overridden"


def test_coord_a_p4():
    """验证 A 类 P=4:DP=P×dp_local=4×1=4(GLM-5 规模)。"""
    override, _ = coordinate_parallelism(_A, device_count=8, pod_count=4, index=3)
    assert override["data_parallel_size"] == 4 and override["data_parallel_start_rank"] == 3


def test_coord_a_raises_cnt_lt_tp():
    """验证 A 类 cnt<TP(装不下一个 TP 组)→ raise。"""
    with pytest.raises(ValueError, match="装不下"):
        coordinate_parallelism(_A, device_count=4, pod_count=2, index=0)


def test_coord_a_raises_non_divisible_no_floor():
    """验证 A 类 cnt%TP≠0 → raise(不向下取整)。"""
    with pytest.raises(ValueError, match="整数倍"):
        coordinate_parallelism(_A, device_count=12, pod_count=2, index=0)


# ─── coordinate_parallelism · B 类(TP 跨 Pod,含 node_rank)───────────────────

_B = {"tensor_parallel_size": 8, "node_rank": 0}


def test_coord_b_dp1_noop():
    """验证 B 类 world_size==TP → DP=1,no-op(tep:TP=8,cnt=4,P=2)。"""
    override, notes = coordinate_parallelism(_B, device_count=4, pod_count=2, index=0)
    assert not override
    assert notes["multinode_dp_layout"] == "TP_across" and notes["multinode_dp_resolved_dp"] == "1"


def test_coord_b_raises_non_divisible():
    """验证 B 类 world_size%TP≠0 → raise(不向下取整):TP=8,cnt=5,P=2(=10)。"""
    with pytest.raises(ValueError, match="整数倍"):
        coordinate_parallelism(_B, device_count=5, pod_count=2, index=0)


def test_coord_b_raises_dp_gt_1():
    """验证 B 类算出 DP>1(多 TP 组)→ raise 暂不支持:TP=8,cnt=8,P=4(=32→DP=4)。"""
    with pytest.raises(ValueError, match="DP=4>1|多 TP 组"):
        coordinate_parallelism(_B, device_count=8, pod_count=4, index=0)


def test_coord_b_p4_dp1_supported():
    """T5.x:B 类 P 不限 2 —— TP=8,cnt=2,P=4 → world_size=8=TP → DP=1 支持(一个 TP 组铺满 4 Pod)。"""
    override, notes = coordinate_parallelism(_B, device_count=2, pod_count=4, index=3)
    assert not override                                  # DP=1 与模板一致 → no-op,不改 DP
    assert notes["multinode_dp_layout"] == "TP_across"
    assert notes["multinode_dp_world_size"] == "8" and notes["multinode_dp_resolved_dp"] == "1"


def test_coord_b_raises_dp_gt_1_more_shapes():
    """T5.x:B 类只要算出 DP>1(多 TP 组)就 raise,与 P/cnt 具体取值无关:2/8 与 4/4 均 world_size=16→DP=2。"""
    for cnt, pod in [(2, 8), (4, 4)]:
        with pytest.raises(ValueError, match="多 TP 组|DP=2>1"):
            coordinate_parallelism(_B, device_count=cnt, pod_count=pod, index=0)


# ─── coordinate_parallelism · PP 保险 / 非法 ─────────────────────────────────

def test_coord_pp_raises():
    """验证选中含 pipeline_parallel_size>1 的策略 → raise"PP 暂不支持"。"""
    with pytest.raises(ValueError, match="PP 暂不支持"):
        coordinate_parallelism(
            {"tensor_parallel_size": 4, "pipeline_parallel_size": 2, "node_rank": 0},
            device_count=4, pod_count=2, index=0,
        )


def test_coord_raises_cnt_le_zero():
    """验证 device_count≤0 → raise。"""
    with pytest.raises(ValueError, match="非法"):
        coordinate_parallelism(_A, device_count=0, pod_count=2, index=0)


def test_coord_a_raises_dp_inconsistent_when_no_device_count():
    """F3 修复:A 类未传 device_count 且 DP≠pod_count×dp_local → raise(防 start_rank 越界)。

    复现 DeepSeek-V3.1(DP=8,dp_local=4,隐含 2 Pod)误部署到 3 Pod 且不带 device-count。
    """
    ec = {"tensor_parallel_size": 8, "data_parallel_size": 8,
          "data_parallel_size_local": 4, "data_parallel_start_rank": 8}
    with pytest.raises(ValueError, match="不一致"):
        coordinate_parallelism(ec, device_count=None, pod_count=3, index=2)


def test_coord_a_consistent_no_device_count_is_noop():
    """F3 边界:A 类未传 device_count 但 DP==pod_count×dp_local(自洽)→ 不 raise,空 override。"""
    ec = {"tensor_parallel_size": 8, "data_parallel_size": 2,
          "data_parallel_size_local": 1, "data_parallel_start_rank": 0}
    assert coordinate_parallelism(ec, device_count=None, pod_count=2, index=0) == ({}, {})


# ─── substitute_literal_placeholders(literal:$local_ip/$node0_ip/$HEAD_IP)───

def test_substitute_literal_ascend_and_nvidia_tokens():
    """验证 $local_ip→RANK_IP、$node0_ip/$HEAD_IP→MASTER_IP 字面替换;仅变更键进 override。"""
    ec = {"data_parallel_address": "$HEAD_IP", "addr2": "$node0_ip", "host": "0.0.0.0"}
    override = substitute_literal_placeholders(ec, rank_ip="10.0.0.2", master_ip="10.0.0.1")
    assert override == {"data_parallel_address": "10.0.0.1", "addr2": "10.0.0.1"}


def test_substitute_literal_leaves_runtime_tokens():
    """验证 runtime 占位($nic_name/$IFACE_NAME)不被字面替换。"""
    env = {"GLOO_SOCKET_IFNAME": "$IFACE_NAME", "HCCL_IF_IP": "$local_ip"}
    override = substitute_literal_placeholders(env, rank_ip="1.2.3.4", master_ip="9.9.9.9")
    assert override == {"HCCL_IF_IP": "1.2.3.4"}  # IFACE_NAME 不动


# ─── runtime_var_commands(runtime:$nic_name / $IFACE_NAME)───────────────────

def test_runtime_var_commands_ascend_nic():
    """验证引用 $nic_name → 产 `nic_name=$(...)`。"""
    assert runtime_var_commands({"GLOO_SOCKET_IFNAME": "$nic_name"}) == [f"nic_name={NIC_DETECT_CMD}"]


def test_runtime_var_commands_nvidia_iface():
    """验证引用 $IFACE_NAME → 产 `IFACE_NAME=$(...)`(变量名 = 去 $)。"""
    assert runtime_var_commands({"NCCL_SOCKET_IFNAME": "$IFACE_NAME"}) == [f"IFACE_NAME={NIC_DETECT_CMD}"]


def test_runtime_var_commands_empty_when_none():
    """验证无 runtime 占位 → 空。"""
    assert not runtime_var_commands({"HCCL_IF_IP": "10.0.0.1"}, {"port": 8077})
