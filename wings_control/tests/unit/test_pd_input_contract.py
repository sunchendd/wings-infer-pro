"""PD 外部输入原子性、role gate 与 placement 契约测试。"""

from __future__ import annotations

import pytest

from wings_ctl.core.models import ClusterPlacement, PdRole
from wings_ctl.pd.input_contract import (
    PD_TOPOLOGY_FIELDS,
    parse_explicit_pd_topology,
    parse_pd_role,
    parse_pd_runtime_input,
)


def _placement() -> ClusterPlacement:
    """构造合法跨 Pod Instance placement(2 Pod,master 在前)。"""
    return ClusterPlacement(
        master_ip="10.0.0.1",
        rank_ip="10.0.0.2",
        node_ips=["10.0.0.1", "10.0.0.2"],
    )


def _singleton_placement() -> ClusterPlacement:
    """构造合法单 Pod Instance placement。"""
    return ClusterPlacement(
        master_ip="10.0.0.10",
        rank_ip="10.0.0.10",
        node_ips=["10.0.0.10"],
    )


def _explicit_env() -> dict[str, str]:
    """构造合法场景 B 六字段。"""
    return {
        "PD_INDEX": "2",
        "PD_PREFILL_DP_SIZE": "4",
        "PD_PREFILL_TP_SIZE": "8",
        "PD_DECODE_DP_SIZE": "32",
        "PD_DECODE_TP_SIZE": "1",
        "DP_SIZE_LOCAL": "16",
    }


def test_parse_pd_role_distinguishes_missing_none_and_roles() -> None:
    """验证 unset 兼容态、显式 none 和 P/D role 不混淆。"""
    assert parse_pd_role(None) == (None, True)
    assert parse_pd_role("none") == (None, False)
    assert parse_pd_role("P") == (PdRole.PREFILL, False)
    assert parse_pd_role("D") == (PdRole.DECODE, False)


@pytest.mark.parametrize("raw", ["", "p", "d", " P ", "unknown"])
def test_parse_pd_role_rejects_empty_or_unknown(raw: str) -> None:
    """验证空串、大小写变体和未知 role 均 fail-fast。"""
    with pytest.raises(ValueError, match="PD_ROLE"):
        parse_pd_role(raw)


def test_six_fields_all_missing_or_all_present() -> None:
    """验证六字段只接受全缺失或全存在。"""
    assert parse_explicit_pd_topology({}) is None
    parsed = parse_explicit_pd_topology(_explicit_env())
    assert parsed is not None
    assert parsed.pd_index == 2
    assert parsed.prefill.dp_size == 4
    assert parsed.decode.tp_size == 1
    assert parsed.dp_size_local == 16


@pytest.mark.parametrize("missing", PD_TOPOLOGY_FIELDS)
def test_six_fields_reject_each_partial_shape(missing: str) -> None:
    """验证缺任意一个原子字段都失败并指出缺失项。"""
    env = _explicit_env()
    del env[missing]
    with pytest.raises(ValueError, match=missing):
        parse_explicit_pd_topology(env)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("PD_INDEX", "-1"),
        ("PD_PREFILL_DP_SIZE", "0"),
        ("PD_PREFILL_TP_SIZE", ""),
        ("PD_DECODE_DP_SIZE", "1.5"),
        ("PD_DECODE_TP_SIZE", "x"),
        ("DP_SIZE_LOCAL", "-2"),
    ],
)
def test_six_fields_reject_invalid_integer_values(name: str, value: str) -> None:
    """验证空值、非整数和非法正负范围都失败。"""
    env = _explicit_env()
    env[name] = value
    with pytest.raises(ValueError, match=name):
        parse_explicit_pd_topology(env)


def test_standard_rejects_residual_pd_fields() -> None:
    """验证标准推理不消费完整或部分 PD topology 残留。"""
    with pytest.raises(ValueError, match="标准推理.*PD_INDEX"):
        parse_pd_runtime_input("none", {"PD_INDEX": "0"}, None, distributed=False)


def test_standard_with_rank_ip_stays_standard() -> None:
    """验证标准推理收到 RANK_IP 不因此进入 multi-node/PD（topology 判定不读 RANK_IP）。"""
    placement = ClusterPlacement(rank_ip="10.0.0.10")
    parsed, missing = parse_pd_runtime_input("none", {}, placement, distributed=False)
    assert parsed is None
    assert missing is False
    # 即使带完整跨 Pod placement，role=none 仍消费为标准推理。
    parsed, _ = parse_pd_runtime_input("none", {}, _placement(), distributed=True)
    assert parsed is None


def test_pd_cross_pod_requires_complete_placement() -> None:
    """验证 PD 跨 Pod(--distributed)必须完整 placement。"""
    # 缺 placement(未下发任何 IP)→ 失败。
    with pytest.raises(ValueError, match="MASTER_IP"):
        parse_pd_runtime_input("D", {}, None, distributed=True)
    # 完整跨 Pod placement → 通过。
    parsed, missing = parse_pd_runtime_input("D", _explicit_env(), _placement(), distributed=True)
    assert missing is False and parsed is not None
    assert parsed.placement.rank_ip == "10.0.0.2"
    # --distributed 不再与 PD 冲突(PD_ROLE 仍是唯一入口)。
    parsed_p, _ = parse_pd_runtime_input("P", _explicit_env(), _placement(), distributed=True)
    assert parsed_p is not None and parsed_p.role == PdRole.PREFILL


def test_pd_single_pod_derives_singleton_from_rank_ip() -> None:
    """验证 PD 单 Pod 缺 MASTER_IP/NODE_IPS 时由 RANK_IP 派生 singleton。"""
    # 只有 RANK_IP → 派生 NODE_IPS=[RANK_IP]、MASTER_IP=RANK_IP。
    parsed, missing = parse_pd_runtime_input("P", {}, ClusterPlacement(rank_ip="10.0.0.10"), distributed=False)
    assert missing is False and parsed is not None
    assert parsed.placement.node_ips == ["10.0.0.10"]
    assert parsed.placement.master_ip == "10.0.0.10"
    # 连 RANK_IP 也没有(placement=None)→ 失败。
    with pytest.raises(ValueError, match="RANK_IP"):
        parse_pd_runtime_input("D", {}, None, distributed=False)
    # 单 Pod 完整 singleton placement → 原样保留。
    parsed2, _ = parse_pd_runtime_input("D", {}, _singleton_placement(), distributed=False)
    assert parsed2 is not None and parsed2.placement.node_ips == ["10.0.0.10"]


@pytest.mark.parametrize(
    "placement",
    [
        ClusterPlacement(master_ip="10.0.0.2", rank_ip="10.0.0.2", node_ips=["10.0.0.1", "10.0.0.2"]),
        ClusterPlacement(master_ip="10.0.0.1", rank_ip="10.0.0.3", node_ips=["10.0.0.1", "10.0.0.2"]),
        ClusterPlacement(master_ip="10.0.0.1", rank_ip="10.0.0.1", node_ips=["10.0.0.1", "10.0.0.1"]),
    ],
)
def test_pd_cross_pod_rejects_invalid_placement(placement: ClusterPlacement) -> None:
    """验证跨 Pod 场景 master 顺序、rank membership 和成员唯一性。"""
    with pytest.raises(ValueError):
        parse_pd_runtime_input("P", _explicit_env(), placement, distributed=True)


def test_pd_cross_pod_rejects_single_member_node_ips() -> None:
    """验证跨 Pod(--distributed)要求 NODE_IPS 至少 2 成员；单成员视为误标失败。"""
    with pytest.raises(ValueError, match="至少 2 个成员"):
        parse_pd_runtime_input(
            "P",
            _explicit_env(),
            ClusterPlacement(master_ip="10.0.0.5", rank_ip="10.0.0.5", node_ips=["10.0.0.5"]),
            distributed=True,
        )


def test_pd_single_pod_partial_rejects_inconsistent_node_ips() -> None:
    """验证单 Pod 若下发 NODE_IPS 必须等于 [RANK_IP]。"""
    with pytest.raises(ValueError, match="NODE_IPS"):
        parse_pd_runtime_input(
            "P",
            {},
            ClusterPlacement(rank_ip="10.0.0.10", node_ips=["10.0.0.10", "10.0.0.11"]),
            distributed=False,
        )


def test_pd_single_pod_partial_rejects_inconsistent_master_ip() -> None:
    """验证单 Pod 若下发 MASTER_IP 必须等于 RANK_IP。"""
    with pytest.raises(ValueError, match="MASTER_IP"):
        parse_pd_runtime_input(
            "D",
            {},
            ClusterPlacement(rank_ip="10.0.0.10", master_ip="10.0.0.99"),
            distributed=False,
        )


def test_pd_single_pod_partial_consistent_is_normalized_singleton() -> None:
    """验证单 Pod 部分下发且一致时归一化为 singleton（NODE_IPS=[RANK_IP]、MASTER_IP=RANK_IP）。"""
    parsed, _ = parse_pd_runtime_input(
        "P",
        {},
        ClusterPlacement(rank_ip="10.0.0.10", master_ip="10.0.0.10", node_ips=["10.0.0.10"]),
        distributed=False,
    )
    assert parsed is not None
    assert parsed.placement.node_ips == ["10.0.0.10"]
    assert parsed.placement.master_ip == "10.0.0.10"
    assert parsed.placement.rank_ip == "10.0.0.10"


def test_pd_builds_normalized_runtime_input() -> None:
    """验证合法 role、六字段和跨 Pod placement 组成规范 PD 输入。"""
    parsed, missing = parse_pd_runtime_input("D", _explicit_env(), _placement(), distributed=True)
    assert missing is False
    assert parsed is not None
    assert parsed.role == PdRole.DECODE
    assert parsed.explicit_topology is not None
    assert parsed.placement.rank_ip == "10.0.0.2"
