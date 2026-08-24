"""Step 3.1-c — multi_node 运行时注入(有 RANK_IP/NODE_IPS → 选 node + R-G + 注入)集成测试。

验证:选本 Pod 节点(R-2 强校验)、占位字面替换(argv 安全)、通信网卡环境变量解析、
R-G DP 调整、产可执行脚本、强校验/越界 raise。
固定输入→固定输出:GLM-4.5(head: cnt=8 复现模板;cnt=16 触发 R-G)。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from wings_ctl.core.topology import Topology
from wings_ctl.core.models import ClusterPlacement, PipelineRequest, Target, UserInput
from wings_ctl.pipeline import run_pipeline

# 原用 ascend-a3 GLM-4.5;config 提交 8b2f5b5 误删 a3 该模型 multi_node 场景(config bug,docs/14)。
# 改指 ascend-a2 GLM-4.5(multi_node 块等价:TP8/2Pod,device_count=16 经 R-G → dp_size4/dp_local2/
# start_rank 0&2,断言不变)。a3 修好后可回指。
_HW = {"hardware_family": "ascend-a2", "device": "ascend", "count": 16}
_MODEL = "GLM-4.5"
_ENGINE = "vllm-ascend"
_ENGINE_VERSION = "v0.18.0"
_NODE_IPS = ["10.0.0.1", "10.0.0.2"]


def _hw(tmp_path: Path) -> Path:
    p = tmp_path / "hardware_info.json"
    p.write_text(json.dumps(_HW), encoding="utf-8")
    return p


def _run(tmp_path, monkeypatch, config_root_real, *, rank_ip, device_count=None, out="out"):
    """带运行时上下文跑 MULTI_NODE 流水线(注入路径)。"""
    monkeypatch.setenv("ENGINE_VERSION", _ENGINE_VERSION)
    monkeypatch.setenv("RANK_IP", rank_ip)
    monkeypatch.setenv("WINGS_START_LOG", str(tmp_path / "wsl.log"))
    return run_pipeline(
        PipelineRequest(
            target=Target(model_name=_MODEL, topology=Topology.MULTI_NODE, engine=_ENGINE),
            hardware_info_path=_hw(tmp_path),
            config_root=config_root_real,
            user_input=UserInput(cli_overrides={"port": 18000}),
            device_count=device_count,
            placement=ClusterPlacement(rank_ip=rank_ip, node_ips=list(_NODE_IPS), master_ip="10.0.0.1"),
        ),
        output_dir=tmp_path / out,
    )


def test_inject_head_promotes_to_top_level_with_literal_ip(config_root_real, tmp_path, monkeypatch):
    """验证 head Pod:选中升顶层、$local_ip 字面替换进 argv、nodes 置 None。"""
    resolved, *_ = _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.0.0.1")
    assert resolved.nodes is None                                   # 已选定,非占位
    assert resolved.engine_config_traces                            # 顶层可执行
    # $local_ip → 字面 rank_ip(argv 安全,无裸 $)
    dpa = resolved.engine_config_traces["data_parallel_address"].final_value
    assert dpa == "10.0.0.1"
    assert resolved.resolution_notes["multi_node_role"] == "head"
    assert resolved.resolution_notes["multi_node_index"] == "0"


def test_inject_rg_scales_dp_on_device_count(config_root_real, tmp_path, monkeypatch):
    """验证 head + device_count=16 触发 R-G:DP=4 / dp_local=2 / start_rank=0,且进 trace 层。"""
    resolved, *_ = _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.0.0.1", device_count=16)
    ec = resolved.engine_config_traces
    assert ec["data_parallel_size"].final_value == 4
    assert ec["data_parallel_size_local"].final_value == 2
    assert ec["data_parallel_start_rank"].final_value == 0
    assert ec["data_parallel_size"].final_layer == "strategy_multinode_dp"   # 改写可追溯
    assert resolved.resolution_notes["multinode_dp_status"] == "overridden"


def test_inject_worker_start_command_executable_and_safe(config_root_real, tmp_path, monkeypatch):
    """验证 worker Pod 产可执行脚本:nic 探测 inline 在 env 前、argv 用字面 master IP、bash -n 过。"""
    _, start_path, repro_path, _ = _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.0.0.2")
    text = start_path.read_text(encoding="utf-8")
    # 可执行(有引擎命令,无占位横幅)
    assert "vllm serve" in text and "RUNTIME INJECTION PENDING" not in text
    # argv data-parallel-address = 字面 master IP(无单引号 $)
    assert "--data-parallel-address 10.0.0.1" in text
    assert "'$local_ip'" not in text and "'$node0_ip'" not in text
    # 通信网卡以本 Pod IP 查询；测试环境没有虚拟集群 IP，按 eth0 兜底。
    assert "GLOO_SOCKET_IFNAME=eth0" in text
    # 语法合法
    subprocess.run(["bash", "-n", str(start_path)], check=True)
    assert "exec vllm serve" in repro_path.read_text(encoding="utf-8")  # repro.sh 仍用 exec


def test_inject_audit_and_startup_log_reflect_injection(config_root_real, tmp_path, monkeypatch):
    """验证 audit 顶层为本 Pod + cluster 注记;wings_start.log 多机行标 injected。"""
    resolved, _, _, audit_path = _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.0.0.2", device_count=16)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert "nodes" not in audit                                     # 非占位,无全集群 nodes 数组
    assert audit["engine_config"]["data_parallel_start_rank"]["final_value"] == 2   # worker index1×dp_local2
    notes = audit["resolution_notes"]
    assert notes["multi_node_role"] == "worker" and notes["multi_node_index"] == "1"
    assert audit["env"]["HCCL_IF_IP"]["final_layer"] == "strategy_network_env"
    assert audit["env"]["GLOO_SOCKET_IFNAME"]["source_path"] == "interface_for_local_ip:fallback_eth0"
    assert notes["network_env_override.interface_discovery"] == "fallback_eth0"
    log_text = (tmp_path / "wsl.log").read_text(encoding="utf-8")
    assert "multi_node: role=worker index=1" in log_text and "injection=injected" in log_text


def test_inject_raises_when_rank_not_in_node_ips(config_root_real, tmp_path, monkeypatch):
    """验证 RANK_IP 不在 NODE_IPS 时强校验 raise(R-2)。"""
    with pytest.raises(ValueError, match="is not in NODE_IPS"):
        _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.9.9.9")


def test_inject_raises_when_tp_not_divides_device_count(config_root_real, tmp_path, monkeypatch):
    """验证 R-G:TP(8)不整除 device-count(12)时 raise。"""
    with pytest.raises(ValueError, match="not divisible"):
        _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.0.0.1", device_count=12)
