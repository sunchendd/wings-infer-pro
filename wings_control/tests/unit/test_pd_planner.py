"""PD 规范 topology、rank 与设备容量测试。"""

from __future__ import annotations

import pytest

from wings_ctl.core.models import (
    ClusterPlacement,
    ExplicitPdTopology,
    ParallelShape,
    PdRole,
    PdRuntimeInput,
)
from wings_ctl.pd.planner import resolve_pd_topology
from wings_ctl.pd.recipe import select_pd_recipe_pair


def _pair(
    policy: str,
    prefill_tp: int = 4,
    decode_tp: int = 2,
    prefill_dp: int | None = None,
    decode_dp: int | None = None,
    prefill_members: int = 1,
    decode_members: int = 1,
):
    """构造正式 nodes schema 的 exact pair。"""
    default_dp = 1 if policy == "derived_1p1d" else 2
    prefill = ParallelShape(prefill_dp or default_dp, prefill_tp)
    decode = ParallelShape(decode_dp or default_dp, decode_tp)
    nodes = []
    for role, tp, members, port in (
        ("prefill", prefill_tp, prefill_members, 36000),
        ("decode", decode_tp, decode_members, 36100),
    ):
        for index in range(members):
            nodes.append(
                {
                    "role": role,
                    "index": index,
                    "engine_config": {
                        "model": "synthetic/model",
                        "port": "$2",
                        "data_parallel_size": "$3",
                        "data_parallel_rank": "$4",
                        "data_parallel_address": "$5",
                        "data_parallel_rpc_port": 12890 if role == "prefill" else 12777,
                        "tensor_parallel_size": "$7",
                        "kv_transfer_config": {
                            "kv_connector": "SyntheticConnector",
                            "kv_role": "kv_producer" if role == "prefill" else "kv_consumer",
                            "kv_port": port,
                            "kv_connector_extra_config": {
                                "prefill": {"dp_size": prefill.dp_size, "tp_size": prefill.tp_size},
                                "decode": {"dp_size": decode.dp_size, "tp_size": decode.tp_size},
                            },
                        },
                    },
                    "env": {},
                }
            )
    model = {
        "scenarios": {"pd_disaggregation": {"strategies": {"approved": {"default_strategy": True, "nodes": nodes}}}}
    }
    return select_pd_recipe_pair(model, policy)


def _placement(nodes: list[str], rank: str | None = None) -> ClusterPlacement:
    """构造已通过输入层验证的 Instance placement。"""
    return ClusterPlacement(master_ip=nodes[0], rank_ip=rank or nodes[0], node_ips=nodes)


def test_derived_1p1d_uses_device_count_for_both_role_tp_and_indices() -> None:
    """验证普通 PD 派生固定 P=0/D=1、DP=1、P/D TP=device-count。"""
    pair = _pair("derived_1p1d", prefill_tp=4, decode_tp=2)
    pd_input = PdRuntimeInput(PdRole.DECODE, None, _placement(["10.0.0.2"]))

    resolved = resolve_pd_topology(pd_input, pair, device_count=2)

    assert resolved.instance_index == 1
    assert resolved.prefill == ParallelShape(dp_size=1, tp_size=2)
    assert resolved.decode == ParallelShape(dp_size=1, tp_size=2)
    assert resolved.rank_start == 0


@pytest.mark.parametrize("device_count", [1, 2, 4, 8, 16])
def test_derived_1p1d_accepts_power_of_two_device_count(device_count: int) -> None:
    """验证普通 PD 不写死硬件上限，并接受正的 2 次幂卡数。"""
    pair = _pair("derived_1p1d")
    pd_input = PdRuntimeInput(PdRole.PREFILL, None, _placement(["10.0.0.1"]))

    resolved = resolve_pd_topology(pd_input, pair, device_count=device_count)

    assert resolved.prefill == ParallelShape(1, device_count)
    assert resolved.decode == ParallelShape(1, device_count)


@pytest.mark.parametrize("device_count", [0, 3, 6, -2])
def test_derived_1p1d_rejects_invalid_device_count(device_count: int) -> None:
    """验证普通 PD 拒绝非正数和非 2 次幂卡数。"""
    pair = _pair("derived_1p1d")
    pd_input = PdRuntimeInput(PdRole.PREFILL, None, _placement(["10.0.0.1"]))

    with pytest.raises(ValueError, match="正整数|2 的幂"):
        resolve_pd_topology(pd_input, pair, device_count=device_count)


def test_derived_1p1d_rejects_multi_pod_instance() -> None:
    """验证普通 1P1D 不接受 multi-Pod Instance。"""
    pair = _pair("derived_1p1d")
    pd_input = PdRuntimeInput(
        PdRole.PREFILL,
        None,
        _placement(["10.0.0.1", "10.0.0.2"]),
    )

    with pytest.raises(ValueError, match="恰好一个 Pod"):
        resolve_pd_topology(pd_input, pair, device_count=8)


def test_explicit_allocation_calculates_member_rank_range() -> None:
    """验证 member_index 与 rank range 只由 Instance placement/local DP 决定。"""
    pair = _pair(
        "explicit_allocation",
        prefill_tp=8,
        decode_tp=1,
        prefill_dp=4,
        decode_dp=32,
        decode_members=2,
    )
    explicit = ExplicitPdTopology(
        pd_index=9,
        prefill=ParallelShape(dp_size=4, tp_size=8),
        decode=ParallelShape(dp_size=32, tp_size=1),
        dp_size_local=16,
    )
    pd_input = PdRuntimeInput(
        PdRole.DECODE,
        explicit,
        _placement(["10.0.0.3", "10.0.0.4"], "10.0.0.4"),
    )

    resolved = resolve_pd_topology(pd_input, pair, device_count=16)

    assert resolved.instance_index == 9
    assert resolved.member_index == 1
    assert resolved.rank_start == 16
    assert resolved.rank_end_exclusive == 32


def test_explicit_allocation_rejects_global_dp_mismatch() -> None:
    """验证 global DP 必须闭合为 Pod 数乘 local DP。"""
    pair = _pair("explicit_allocation", prefill_dp=3, decode_dp=2, prefill_members=2)
    explicit = ExplicitPdTopology(
        pd_index=0,
        prefill=ParallelShape(dp_size=3, tp_size=4),
        decode=ParallelShape(dp_size=2, tp_size=2),
        dp_size_local=1,
    )
    pd_input = PdRuntimeInput(
        PdRole.PREFILL,
        explicit,
        _placement(["10.0.0.1", "10.0.0.2"]),
    )

    with pytest.raises(ValueError, match="global DP closure"):
        resolve_pd_topology(pd_input, pair, device_count=8)


def test_explicit_allocation_accepts_custom_homogeneous_mpnd_shape() -> None:
    """验证 custom mPnD 只受 closure 和满卡约束，不受 recipe 示例 shape 限制。"""
    pair = _pair(
        "explicit_allocation",
        prefill_tp=4,
        decode_tp=2,
        prefill_dp=2,
        decode_dp=4,
    )
    explicit = ExplicitPdTopology(
        pd_index=7,
        prefill=ParallelShape(dp_size=8, tp_size=2),
        decode=ParallelShape(dp_size=4, tp_size=4),
        dp_size_local=2,
    )
    pd_input = PdRuntimeInput(
        PdRole.PREFILL,
        explicit,
        _placement(
            ["10.0.0.5", "10.0.0.6", "10.0.0.7", "10.0.0.8"],
            "10.0.0.8",
        ),
    )

    resolved = resolve_pd_topology(pd_input, pair, device_count=4)

    assert resolved.instance_index == 7
    assert resolved.prefill == ParallelShape(dp_size=8, tp_size=2)
    assert resolved.decode == ParallelShape(dp_size=4, tp_size=4)
    assert resolved.member_index == 3
    assert resolved.rank_start == 6
    assert resolved.rank_end_exclusive == 8


def test_explicit_allocation_rejects_idle_devices() -> None:
    """验证 PD 大 EP 必须让 TP 和 local DP 使用当前 Pod 的全部设备。"""
    pair = _pair("explicit_allocation", prefill_dp=2, decode_dp=4, prefill_members=2)
    explicit = ExplicitPdTopology(
        pd_index=0,
        prefill=ParallelShape(dp_size=2, tp_size=2),
        decode=ParallelShape(dp_size=4, tp_size=2),
        dp_size_local=2,
    )
    pd_input = PdRuntimeInput(PdRole.PREFILL, explicit, _placement(["10.0.0.1"]))

    with pytest.raises(ValueError, match="满卡闭合"):
        resolve_pd_topology(pd_input, pair, device_count=8)


def test_explicit_allocation_rejects_insufficient_devices() -> None:
    """验证 role TP 乘 local DP 不得超过当前 Pod device_count。"""
    pair = _pair("explicit_allocation", prefill_tp=4, decode_tp=2, prefill_dp=2, decode_dp=2)
    explicit = ExplicitPdTopology(
        pd_index=0,
        prefill=ParallelShape(dp_size=2, tp_size=4),
        decode=ParallelShape(dp_size=2, tp_size=2),
        dp_size_local=2,
    )
    pd_input = PdRuntimeInput(PdRole.PREFILL, explicit, _placement(["10.0.0.1"]))

    with pytest.raises(ValueError, match="卡数不足"):
        resolve_pd_topology(pd_input, pair, device_count=4)


@pytest.mark.parametrize("device_count", [True, 0, -1])
def test_explicit_allocation_rejects_invalid_device_count(device_count: int) -> None:
    """验证显式分配拒绝布尔值和非正卡数。"""
    pair = _pair("explicit_allocation", prefill_dp=2, decode_dp=2)
    explicit = ExplicitPdTopology(
        pd_index=0,
        prefill=ParallelShape(dp_size=1, tp_size=1),
        decode=ParallelShape(dp_size=1, tp_size=1),
        dp_size_local=1,
    )
    pd_input = PdRuntimeInput(PdRole.PREFILL, explicit, _placement(["10.0.0.1"]))

    with pytest.raises(ValueError, match="device_count 必须是正整数"):
        resolve_pd_topology(pd_input, pair, device_count=device_count)


def test_pd_topology_requires_device_count() -> None:
    """验证 PD 容量校验不从硬件猜卡数，必须显式输入。"""
    pair = _pair("derived_1p1d")
    pd_input = PdRuntimeInput(PdRole.PREFILL, None, _placement(["10.0.0.1"]))

    with pytest.raises(ValueError, match="device_count"):
        resolve_pd_topology(pd_input, pair, device_count=None)


@pytest.mark.parametrize(
    (
        "case",
        "role",
        "prefill",
        "decode",
        "nodes",
        "member_index",
        "local_dp",
        "device_count",
        "expected_rank_start",
    ),
    [
        ("glm51_a3_p", PdRole.PREFILL, ParallelShape(2, 16), ParallelShape(16, 4), 2, 1, 1, 16, 1),
        ("glm51_a3_d", PdRole.DECODE, ParallelShape(2, 16), ParallelShape(16, 4), 4, 3, 4, 16, 12),
        ("dsv4_a3_p", PdRole.PREFILL, ParallelShape(4, 4), ParallelShape(16, 1), 1, 0, 4, 16, 0),
        ("dsv4_a3_d", PdRole.DECODE, ParallelShape(4, 4), ParallelShape(16, 1), 1, 0, 16, 16, 0),
        ("dsv4_a2_p", PdRole.PREFILL, ParallelShape(8, 1), ParallelShape(32, 1), 1, 0, 8, 8, 0),
        ("dsv4_a2_d", PdRole.DECODE, ParallelShape(8, 1), ParallelShape(32, 1), 4, 3, 8, 8, 24),
    ],
)
def test_official_v023_shapes_fit_explicit_allocation(
    case: str,
    role: PdRole,
    prefill: ParallelShape,
    decode: ParallelShape,
    nodes: int,
    member_index: int,
    local_dp: int,
    device_count: int,
    expected_rank_start: int,
) -> None:
    """验证有官方证据的 GLM5.1 A3、DSV4 A2/A3 topology 可被 schema 无损表达。"""
    pair = _pair(
        "explicit_allocation",
        prefill_tp=prefill.tp_size,
        decode_tp=decode.tp_size,
        prefill_dp=prefill.dp_size,
        decode_dp=decode.dp_size,
        prefill_members=nodes if role is PdRole.PREFILL else 1,
        decode_members=nodes if role is PdRole.DECODE else 1,
    )
    node_ips = [f"10.0.0.{index + 1}" for index in range(nodes)]
    explicit = ExplicitPdTopology(
        pd_index=4 if case == "dsv4_a2_d" else 0,
        prefill=prefill,
        decode=decode,
        dp_size_local=local_dp,
    )
    pd_input = PdRuntimeInput(role, explicit, _placement(node_ips, node_ips[member_index]))

    resolved = resolve_pd_topology(pd_input, pair, device_count=device_count)

    assert resolved.rank_start == expected_rank_start
    assert resolved.rank_end_exclusive == expected_rank_start + local_dp
