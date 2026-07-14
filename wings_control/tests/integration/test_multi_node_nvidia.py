"""Step:nvidia `head`/`worker` 形态 multi_node 集成测试(docs/32 多形态重设计)。

验证 vllm(nvidia)的 head/worker 直接键形态(全仓 4039,主流)端到端可用:
选 head/worker、node_rank=index、`$HEAD_IP`→MASTER_IP 字面、`$IFACE_NAME`→运行时 inline、
TP 跨 Pod(tep,DP=1)、worker --headless。固定输入:DeepSeek-V4-Pro-fp8(vllm/h100,默认 tep;
传完整变体名 variant_name 避免家族级歧义,docs/48)。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from wings_ctl.core.topology import Topology
from wings_ctl.core.models import ClusterPlacement, PipelineRequest, Target
from wings_ctl.pipeline import run_pipeline

_HW = {"hardware_family": "h100", "device": "nvidia", "count": 8}
_MODEL = "DeepSeek-V4-Pro-fp8"  # 完整变体名(variant_name);传家族名 DeepSeek-V4-Pro 会命中 fp8/dspark 歧义
_ENGINE = "vllm"
_NODE_IPS = ["10.0.0.1", "10.0.0.2"]


def _hw(tmp_path: Path) -> Path:
    p = tmp_path / "hw.json"
    p.write_text(json.dumps(_HW), encoding="utf-8")
    return p


def _run(tmp_path, monkeypatch, config_root_real, *, rank_ip, tag):
    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    monkeypatch.setenv("WINGS_START_LOG", str(tmp_path / f"{tag}.log"))
    return run_pipeline(
        PipelineRequest(
            target=Target(model_name=_MODEL, topology=Topology.MULTI_NODE, engine=_ENGINE),
            hardware_info_path=_hw(tmp_path),
            config_root=config_root_real,
            device_count=8,
            placement=ClusterPlacement(rank_ip=rank_ip, node_ips=list(_NODE_IPS), master_ip="10.0.0.1"),
        ),
        output_dir=tmp_path / tag,
    )


def test_nvidia_head_worker_schema_supported(config_root_real, tmp_path, monkeypatch):
    """验证 nvidia head/worker 形态被识别并选对节点(head index0 / worker index1),非占位。"""
    head, *_ = _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.0.0.1", tag="head")
    worker, *_ = _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.0.0.2", tag="worker")
    assert head.nodes is None and worker.nodes is None         # 已选定升顶层,非占位
    assert head.resolution_notes["multi_node_role"] == "head"
    assert worker.resolution_notes["multi_node_role"] == "worker"
    # TP 跨 Pod(tep):TP=16 静态;DP=world_size//TP=16//16=1
    assert head.engine_config_traces["tensor_parallel_size"].final_value == 16


def test_nvidia_worker_argv_node_rank_and_literal_master(config_root_real, tmp_path, monkeypatch):
    """验证 worker 产可执行脚本:node_rank=1、master_addr=字面 MASTER_IP、--headless、$IFACE_NAME 运行时。"""
    _, start_path, repro_path, _ = _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.0.0.2", tag="worker")
    text = start_path.read_text(encoding="utf-8")
    assert "exec vllm serve" in text and "RUNTIME INJECTION PENDING" not in text
    # B 类 per-Pod 身份键:node_rank=index=1
    assert "--node-rank 1" in text
    # $HEAD_IP → 字面 MASTER_IP(argv 安全,无裸 $)
    assert "--master-addr 10.0.0.1" in text and "'$HEAD_IP'" not in text
    assert "--headless" in text
    # $IFACE_NAME 运行时探测 inline,在 env 之前;env 里双引号引用
    assert "IFACE_NAME=$(awk" in text
    assert text.index("IFACE_NAME=$(awk") < text.index("export ")
    assert 'NCCL_SOCKET_IFNAME="$IFACE_NAME"' in text
    subprocess.run(["bash", "-n", str(start_path)], check=True)
    assert "exec vllm serve" in repro_path.read_text(encoding="utf-8")


def test_nvidia_head_argv_node_rank_0_no_headless(config_root_real, tmp_path, monkeypatch):
    """验证 head:node_rank=0、无 --headless。"""
    _, start_path, _, _ = _run(tmp_path, monkeypatch, config_root_real, rank_ip="10.0.0.1", tag="head")
    text = start_path.read_text(encoding="utf-8")
    assert "--node-rank 0" in text
    # head 段无 headless(worker 才有)
    head_exec = [ln for ln in text.splitlines() if ln.startswith("exec vllm serve")][0]
    assert "--headless" not in head_exec


def test_nvidia_placeholder_without_runtime_ctx(config_root_real, tmp_path, monkeypatch):
    """验证无运行时上下文 → nvidia head/worker 也产占位脚本(nodes 展开,exit 3,不可执行)。"""
    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    monkeypatch.setenv("WINGS_START_LOG", str(tmp_path / "ph.log"))
    resolved, start_path, _, _ = run_pipeline(
        PipelineRequest(
            target=Target(model_name=_MODEL, topology=Topology.MULTI_NODE, engine=_ENGINE),
            hardware_info_path=_hw(tmp_path),
            config_root=config_root_real,
        ),
        output_dir=tmp_path / "ph",
    )
    assert resolved.nodes is not None and [n.role for n in resolved.nodes] == ["head", "worker"]
    text = start_path.read_text(encoding="utf-8")
    assert "exit 3" in text and "\nexec " not in text
