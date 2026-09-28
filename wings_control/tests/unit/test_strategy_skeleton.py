from __future__ import annotations

import pytest

from wings_ctl.core.models import PdRole
from wings_ctl.core.topology import Topology
from wings_ctl.strategy.post_template import (
    TRANSFORMS,
    device_count_transform,
    post_template_strategy,
)
from wings_ctl.strategy.pre_template import pre_template_strategy


def test_pre_template_no_distributed_is_standalone() -> None:
    """无 distributed → standalone;engine 透传(各引擎名均如此)。"""
    for engine in ("vllm", "vllm-ascend", "custom-engine"):
        out_engine, out_topology = pre_template_strategy(engine)
        assert out_engine == engine
        assert out_topology == Topology.STANDALONE


def test_pre_template_distributed_with_master_ip_is_multi_node() -> None:
    """distributed=True + master_ip → MULTI_NODE。"""
    out_engine, out_topology = pre_template_strategy(
        "vllm-ascend", distributed=True, master_ip="10.0.0.1",
    )
    assert out_engine == "vllm-ascend"
    assert out_topology == Topology.MULTI_NODE


def test_pre_template_distributed_missing_master_ip_raises_valueerror() -> None:
    """distributed=True 但缺 master_ip → ValueError(早失败,cli 转 parser.error)。"""
    with pytest.raises(ValueError, match="MASTER_IP"):
        pre_template_strategy("vllm", distributed=True, master_ip=None)


@pytest.mark.parametrize("master_ip", [None, ""])
@pytest.mark.parametrize("distributed", [True, False])
def test_pre_template_mooncake_master_pod_exempts_master_ip(
    master_ip: str | None, distributed: bool
) -> None:
    """Mooncake master 专属 Pod:豁免标准多机的 MASTER_IP 强校验,仍推导 MULTI_NODE。

    master Pod 不属于推理集群(无 RANK_IP/NODE_IPS/MASTER_IP),但须与 engine Pod
    同拓扑值驱动 smart-accel 匹配/降级判定(决策一致性由构造保证)。
    distributed 两种取值都归 MULTI_NODE(身份是部署层事实,优先于标准分布式语义)。
    """
    assert pre_template_strategy(
        "vllm",
        distributed=distributed,
        master_ip=master_ip,
        is_mooncake_master=True,
    ) == ("vllm", Topology.MULTI_NODE)


def test_pre_template_non_master_pod_keeps_master_ip_gate() -> None:
    """非 master Pod(缺省 is_mooncake_master=False)守既有 fail-fast,不因新参数放宽。"""
    with pytest.raises(ValueError, match="MASTER_IP"):
        pre_template_strategy(
            "vllm", distributed=True, master_ip=None, is_mooncake_master=False
        )


def test_pre_template_pd_role_outranks_mooncake_master() -> None:
    """pd_role 优先级高于 master Pod 判定(PD_ROLE 与 IS_MOONCAKE_MASTER 互斥,
    真实部署不会同时出现;此断言固定优先级顺序,防止未来调整时语义漂移)。"""
    assert pre_template_strategy(
        "vllm", pd_role=PdRole.PREFILL, distributed=True, is_mooncake_master=True
    ) == ("vllm", Topology.PD_PREFILL)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (PdRole.PREFILL, Topology.PD_PREFILL),
        (PdRole.DECODE, Topology.PD_DECODE),
    ],
)
def test_pre_template_pd_role_selects_role_topology(role: PdRole, expected: Topology) -> None:
    """验证规范化 P/D role 映射到对应 runtime topology。"""
    assert pre_template_strategy("vllm", pd_role=role) == ("vllm", expected)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (PdRole.PREFILL, Topology.PD_PREFILL),
        (PdRole.DECODE, Topology.PD_DECODE),
    ],
)
def test_pre_template_pd_role_with_distributed_selects_role_topology(
    role: PdRole, expected: Topology
) -> None:
    """验证 PD + --distributed 不再冲突：PD_ROLE 仍是唯一 PD 入口，distributed 不改 PD 判断。"""
    assert pre_template_strategy("vllm", pd_role=role, distributed=True) == ("vllm", expected)
    assert pre_template_strategy("vllm", pd_role=role, distributed=False) == ("vllm", expected)


def test_post_template_strategy_returns_overrides_and_notes_tuple() -> None:
    """新契约:返回 (override_layer, notes),不原地改 engine_config。"""
    engine_config = {
        "model": "acme/model",
        "tensor_parallel_size": 4,
        "data_parallel_size": 4,
    }
    # 无 device_count → 链路不触发,override/notes 皆空,且不动 engine_config
    overrides, notes = post_template_strategy(engine_config, {"topology": Topology.STANDALONE})
    assert not overrides
    assert not notes
    assert "data_parallel_size" in engine_config and engine_config["data_parallel_size"] == 4


def test_post_template_transforms_chain_has_device_count() -> None:
    assert TRANSFORMS == [device_count_transform]

