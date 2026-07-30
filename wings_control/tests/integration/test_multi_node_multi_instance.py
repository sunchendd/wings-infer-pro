"""多 Pod 多实例(K 副本)演示测试 —— 证明"多实例 = 每实例独立跑多机流程"成立(docs/31 §8)。

框架无"多实例"专门逻辑:每个实例是一次独立的多 Pod 单实例部署,每 Pod 各跑一次,
NODE_IPS 按**实例** scoped。本测试模拟 2 实例 × 2 Pod(各自 NODE_IPS / MASTER_IP),
逐 Pod 跑流水线,断言:每 Pod 选对 head/worker、占位填本实例的 IP、served_model_name 一致、
两实例互不干扰。固定输入→固定输出:GLM-4.5(multi_node,head+worker)。
"""

from __future__ import annotations

import json
from pathlib import Path

from wings_ctl.core.topology import Topology
from wings_ctl.core.models import ClusterPlacement, PipelineRequest, Target, UserInput
from wings_ctl.pipeline import run_pipeline

# 改指 ascend-a2 GLM-4.5:config 8b2f5b5 误删 a3 该模型 multi_node 场景(config bug,docs/14);
# a2 multi_node 块等价,断言不变。a3 修好后可回指。
_HW = {"hardware_family": "ascend-a2", "device": "ascend", "count": 16}
_MODEL = "GLM-4.5"
_ENGINE = "vllm-ascend"

# 两个实例,各自一套 NODE_IPS(scoped 到本实例的 2 个 Pod);MASTER_IP = 各实例 head。
_INSTANCES = {
    "instanceA": {"master": "10.0.1.1", "node_ips": ["10.0.1.1", "10.0.1.2"]},
    "instanceB": {"master": "10.0.2.1", "node_ips": ["10.0.2.1", "10.0.2.2"]},
}


def _hw(tmp_path: Path) -> Path:
    p = tmp_path / "hardware_info.json"
    p.write_text(json.dumps(_HW), encoding="utf-8")
    return p


def _run_pod(tmp_path, monkeypatch, config_root_real, *, inst: str, rank_ip: str, tag: str):
    """以某实例某 Pod 的运行时上下文跑一次流水线,返回 ResolvedConfig。"""
    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    monkeypatch.setenv("WINGS_START_LOG", str(tmp_path / f"{tag}.log"))
    meta = _INSTANCES[inst]
    resolved, *_ = run_pipeline(
        PipelineRequest(
            target=Target(model_name=_MODEL, topology=Topology.MULTI_NODE, engine=_ENGINE),
            hardware_info_path=_hw(tmp_path),
            config_root=config_root_real,
            user_input=UserInput(cli_overrides={"port": 18000}),
            placement=ClusterPlacement(
                rank_ip=rank_ip, node_ips=list(meta["node_ips"]), master_ip=meta["master"]
            ),
        ),
        output_dir=tmp_path / tag,
    )
    return resolved


def test_two_instances_each_select_correct_roles_independently(
    config_root_real, tmp_path, monkeypatch
):
    """验证 2 实例 × 2 Pod:各实例 head/worker 选对、占位填本实例 IP、served 一致、互不干扰。"""
    # instanceA:head=10.0.1.1, worker=10.0.1.2
    a_head = _run_pod(tmp_path, monkeypatch, config_root_real, inst="instanceA", rank_ip="10.0.1.1", tag="a_head")
    a_worker = _run_pod(tmp_path, monkeypatch, config_root_real, inst="instanceA", rank_ip="10.0.1.2", tag="a_worker")
    # instanceB:head=10.0.2.1, worker=10.0.2.2
    b_head = _run_pod(tmp_path, monkeypatch, config_root_real, inst="instanceB", rank_ip="10.0.2.1", tag="b_head")
    b_worker = _run_pod(tmp_path, monkeypatch, config_root_real, inst="instanceB", rank_ip="10.0.2.2", tag="b_worker")

    # 角色 / index 各自正确
    assert a_head.resolution_notes["multi_node_role"] == "head"
    assert a_head.resolution_notes["multi_node_index"] == "0"
    assert a_worker.resolution_notes["multi_node_role"] == "worker"
    assert a_worker.resolution_notes["multi_node_index"] == "1"
    assert b_head.resolution_notes["multi_node_role"] == "head"
    assert b_worker.resolution_notes["multi_node_role"] == "worker"

    # 占位填的是**本实例**的 IP(worker 的 data_parallel_address = 本实例 head/master)
    assert a_worker.engine_config_traces["data_parallel_address"].final_value == "10.0.1.1"
    assert b_worker.engine_config_traces["data_parallel_address"].final_value == "10.0.2.1"
    assert a_head.engine_config_traces["data_parallel_address"].final_value == "10.0.1.1"   # head $local_ip=自身

    # 同一模型 K 副本:served_model_name 跨实例/节点一致(取 recipe 值,4 份相同),且均已注入
    served = {r.engine_config_traces["served_model_name"].final_value for r in (a_head, a_worker, b_head, b_worker)}
    assert len(served) == 1                             # K 副本服务同一模型,served 名一致
    for r in (a_head, a_worker, b_head, b_worker):
        assert r.nodes is None                          # 均已注入(非占位)

    # 两实例互不干扰:各自记录本实例的 node_ips
    assert a_head.resolution_notes["multi_node_node_ips"] == "10.0.1.1,10.0.1.2"
    assert b_head.resolution_notes["multi_node_node_ips"] == "10.0.2.1,10.0.2.2"


def test_each_instance_pod_produces_executable_script(config_root_real, tmp_path, monkeypatch):
    """验证每实例每 Pod 都产出可执行 start_command.sh(含本实例字面 IP,无占位残留)。"""
    out = tmp_path / "b_worker"
    _run_pod(tmp_path, monkeypatch, config_root_real, inst="instanceB", rank_ip="10.0.2.2", tag="b_worker")
    text = (out / "start_command.sh").read_text(encoding="utf-8")
    assert "vllm serve" in text and "RUNTIME INJECTION PENDING" not in text
    assert "--data-parallel-address 10.0.2.1" in text       # 本实例 head 字面 IP
    assert "'$local_ip'" not in text and "'$node0_ip'" not in text
