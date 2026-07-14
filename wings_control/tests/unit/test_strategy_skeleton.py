from __future__ import annotations

import pytest

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


def test_pre_template_pd_role_is_reserved_not_implemented() -> None:
    """pd_role 置位 → 预留 NotImplementedError(PD 分离本期不实现)。"""
    with pytest.raises(NotImplementedError, match="PD"):
        pre_template_strategy("vllm", pd_role="P")


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

