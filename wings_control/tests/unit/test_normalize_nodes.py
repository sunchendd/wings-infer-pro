"""normalize_nodes 单测(docs/32 §2.1):形态归一唯一入口的 if-形态分发 + fail-fast。

覆盖 docs/32 §5.1 T1.1/T1.2/T1.3:ascend nodes[] / nvidia head·worker / 未知形态。
"""

from __future__ import annotations

import pytest

from wings_ctl.core.config_resolver import NodeSpec, normalize_nodes


def test_normalize_nodes_ascend_list():
    """T1.1:ascend nodes[] → 逐项 NodeSpec(条数=nodes 数,index/role 取原标)。"""
    strategy = {"nodes": [
        {"role": "head", "index": 0, "engine_config": {"tensor_parallel_size": 8}},
        {"role": "worker", "index": 1, "engine_config": {"tensor_parallel_size": 8}},
    ]}
    specs = normalize_nodes(strategy, "scenarios.multi_node.strategies.s", pod_count=2)
    assert specs is not None and len(specs) == 2
    assert all(isinstance(s, NodeSpec) for s in specs)
    assert (specs[0].role, specs[0].index) == ("head", 0)
    assert specs[1].engine_config_source_prefix == (
        "scenarios.multi_node.strategies.s.nodes[1].engine_config"
    )


def test_normalize_nodes_head_worker_reuse_and_node_rank():
    """T1.2:nvidia head/worker → head + worker×(P-1) 复用展开,B 类 worker.node_rank=index。"""
    strategy = {
        "head": {"engine_config": {"tensor_parallel_size": 16, "node_rank": 0}},
        "worker": {"engine_config": {"tensor_parallel_size": 16, "node_rank": 0}},
    }
    specs = normalize_nodes(strategy, "scenarios.multi_node.strategies.tep", pod_count=3)
    assert specs is not None and len(specs) == 3                # head + 2 worker
    assert specs[0].role == "head" and specs[0].index == 0
    assert [s.engine_config["node_rank"] for s in specs[1:]] == [1, 2]  # 复用模板按 index 改写


def test_normalize_nodes_head_worker_dp_across_start_rank():
    """T1.2(A 类):head/worker 含 data_parallel_start_rank → worker 写 index×dp_local。"""
    strategy = {
        "head": {"engine_config": {"tensor_parallel_size": 8, "data_parallel_size_local": 2,
                                   "data_parallel_start_rank": 0}},
        "worker": {"engine_config": {"tensor_parallel_size": 8, "data_parallel_size_local": 2,
                                     "data_parallel_start_rank": 0}},
    }
    specs = normalize_nodes(strategy, "p", pod_count=3)
    assert [s.engine_config["data_parallel_start_rank"] for s in specs[1:]] == [2, 4]  # index×2


def test_normalize_nodes_unknown_form_returns_none():
    """T1.4:既无 nodes[] 又无 head/worker(单段形态)→ None,交调用方按单段处理。"""
    assert normalize_nodes({"engine_config": {"model": "m"}}, "p", pod_count=2) is None


def test_normalize_nodes_worker_without_head_raises():
    """T1.3:形态像多机(有 worker 却缺 head)→ fail-fast raise,列出 strategy 键。"""
    with pytest.raises(ValueError, match="lacks 'head'"):
        normalize_nodes({"worker": {"engine_config": {}}}, "p", pod_count=2)


def test_normalize_nodes_head_worker_raises_when_nnodes_mismatch():
    """D3 修复:head/worker 含静态 nnodes 与运行时 pod_count(len NODE_IPS)不一致 → raise。

    复现 MiMo(nnodes=2)误部署到 3 Pod:不自动改 nnodes,fail-fast。
    """
    strategy = {
        "head": {"engine_config": {"tensor_parallel_size": 8, "nnodes": 2, "node_rank": 0}},
        "worker": {"engine_config": {"tensor_parallel_size": 8, "nnodes": 2, "node_rank": 0}},
    }
    with pytest.raises(ValueError, match="nnodes|Cluster size"):
        normalize_nodes(strategy, "p", pod_count=3)


def test_normalize_nodes_head_worker_nnodes_match_ok():
    """D3 边界:nnodes==pod_count(自洽)→ 正常展开,不 raise。"""
    strategy = {
        "head": {"engine_config": {"tensor_parallel_size": 8, "nnodes": 2, "node_rank": 0}},
        "worker": {"engine_config": {"tensor_parallel_size": 8, "nnodes": 2, "node_rank": 0}},
    }
    specs = normalize_nodes(strategy, "p", pod_count=2)
    assert specs is not None and len(specs) == 2
    assert [s.engine_config["node_rank"] for s in specs] == [0, 1]
