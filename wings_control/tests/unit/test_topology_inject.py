"""TopologyRuntimeInject 纯逻辑单测(docs/32):选 node / R-G v3 协调 / 占位填充。"""

from __future__ import annotations

import pytest

from wings_ctl.strategy.topology_inject import (
    LAYOUT_DP_ACROSS,
    LAYOUT_TP_ACROSS,
    build_rendezvous_address_override,
    coordinate_parallelism,
    detect_layout,
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


def test_coord_b_uses_world_size_as_tp():
    """验证 B 类始终使用 world_size 作为 TP，并保持模板 DP。"""
    override, notes = coordinate_parallelism(
        {"tensor_parallel_size": 8, "data_parallel_size": 3, "node_rank": 0},
        device_count=4, pod_count=2, index=0,
    )
    assert override == {}
    assert notes["multinode_dp_resolved_tp"] == "8"
    assert notes["multinode_dp_resolved_dp"] == "3"


def test_coord_b_uses_all_cards_when_non_divisible():
    """验证 B 类 world_size 不整除模板 TP 时使用全部卡并保持模板 DP。"""
    override, notes = coordinate_parallelism(
        {"tensor_parallel_size": 6, "data_parallel_size": 3, "node_rank": 0},
        device_count=4, pod_count=2, index=0,
    )
    assert override == {"tensor_parallel_size": 8}
    assert notes["multinode_dp_status"] == "warning_tp_overridden"
    assert notes["multinode_dp_resolved_tp"] == "8"
    assert notes["multinode_dp_resolved_dp"] == "3"


def test_coord_b_non_power_of_two_override_is_rejected():
    """验证 B 类非整除时调整后的 world_size 仍必须是 2 的幂。"""
    with pytest.raises(ValueError, match="2 的幂"):
        coordinate_parallelism(_B, device_count=5, pod_count=2, index=0)


def test_coord_b_non_divisible_keeps_template_dp(caplog):
    """验证 TP 被调整时日志提示下发参数与模板不一致，且 DP 不变。"""
    ec = {"tensor_parallel_size": 6, "data_parallel_size": 3, "node_rank": 0}
    with caplog.at_level("WARNING"):
        override, notes = coordinate_parallelism(ec, device_count=8, pod_count=1, index=0)
    assert override == {"tensor_parallel_size": 8}
    assert notes["multinode_dp_resolved_dp"] == "3"
    assert "下发参数与模板不一致" in caplog.text


def test_coord_b_shrinks_tp_when_world_size_is_smaller():
    """验证 B 类 world_size<TP 时使用全部卡并保持模板 DP。"""
    override, notes = coordinate_parallelism(
        {"tensor_parallel_size": 8, "data_parallel_size": 3, "node_rank": 0},
        device_count=1, pod_count=2, index=0,
    )
    assert override == {"tensor_parallel_size": 2}
    assert notes["multinode_dp_status"] == "warning_tp_overridden"
    assert notes["multinode_dp_resolved_tp"] == "2"
    assert notes["multinode_dp_resolved_dp"] == "3"


def test_coord_b_shrink_keeps_template_dp():
    """验证 TP 收缩时也保持模板 DP，不改写 DP。"""
    override, notes = coordinate_parallelism(
        {"tensor_parallel_size": 8, "data_parallel_size": 3, "node_rank": 0},
        device_count=1, pod_count=2, index=0,
    )
    assert override == {"tensor_parallel_size": 2}
    assert notes["multinode_dp_resolved_dp"] == "3"


def test_coord_b_rejects_non_power_of_two_shrink():
    """验证 B 类 world_size<TP 且非 2 的幂时失败。"""
    with pytest.raises(ValueError, match="2 的幂"):
        coordinate_parallelism(_B, device_count=3, pod_count=2, index=0)


def test_coord_b_keeps_dp_when_world_size_equals_tp():
    """验证 B 类 world_size 等于模板 TP 时也不修改 DP。"""
    override, notes = coordinate_parallelism(
        {"tensor_parallel_size": 8, "data_parallel_size": 3, "node_rank": 0},
        device_count=2, pod_count=4, index=3,
    )
    assert override == {}
    assert notes["multinode_dp_resolved_dp"] == "3"


def test_coord_b_warns_multiple_tp_groups_without_changing_dp(caplog):
    """验证 B 类多 TP 组只告警，TP 使用 world_size，DP 保持模板值。"""
    ec = {"tensor_parallel_size": 8, "data_parallel_size": 3, "node_rank": 0}
    with caplog.at_level("WARNING"):
        override, notes = coordinate_parallelism(ec, device_count=4, pod_count=4, index=0)
    assert override == {"tensor_parallel_size": 16}
    assert notes["multinode_dp_resolved_dp"] == "3"
    assert "下发参数与模板不一致" in caplog.text


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
    ec = {"data_parallel_address": "${HEAD_IP}:5000", "addr2": "$node0_ip", "host": "0.0.0.0"}
    override = substitute_literal_placeholders(ec, rank_ip="10.0.0.2", master_ip="10.0.0.1")
    assert override == {"data_parallel_address": "10.0.0.1:5000", "addr2": "10.0.0.1"}


def test_sglang_rendezvous_uses_runtime_master_ip_and_recipe_port():
    """SGLang 多机必须忽略 recipe host，仅沿用其 rendezvous 端口。"""
    override = build_rendezvous_address_override(
        {"dist_init_addr": "192.168.1.100:28030"},
        engine="sglang",
        master_ip="10.0.0.1",
    )
    assert override == {"dist_init_addr": "10.0.0.1:28030"}


@pytest.mark.parametrize(
    "recipe_value",
    [None, "", "host", "host:abc", "host:0", "host:65536"],
)
def test_sglang_rendezvous_requires_valid_recipe_port(recipe_value):
    """SGLang 多机 recipe 必须给出合法 host:port，以避免静默选择错误端口。"""
    with pytest.raises(ValueError, match="dist_init_addr"):
        build_rendezvous_address_override(
            {"dist_init_addr": recipe_value},
            engine="sglang",
            master_ip="10.0.0.1",
        )


def test_vllm_has_no_rendezvous_override_contract():
    assert build_rendezvous_address_override(
        {"dist_init_addr": "192.168.1.100:28030"},
        engine="vllm",
        master_ip="10.0.0.1",
    ) == {}


def test_sglang_two_node_tp_across_uses_native_tp_key():
    override, notes = coordinate_parallelism(
        {"model": "m", "tp_size": 32, "node_rank": 0},
        engine="sglang",
        device_count=8,
        pod_count=2,
        index=0,
    )

    assert override == {"tp_size": 16}
    assert notes["multinode_dp_resolved_dp"] == "1"
