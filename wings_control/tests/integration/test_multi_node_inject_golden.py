"""multi_node 注入态(3.1-c)golden 回归:逐字钉住每 Pod 生成的 start_command.sh。

为什么:注入态是输出最复杂的一块(选本 Pod + R-G 协调 DP + 占位填真实 IP + inline NIC + env 注入),
最容易被重构悄悄改坏。这里把"相同输入 → 逐字相同 start_command.sh"冻住,覆盖
两种布局 × head/worker:
  - MiMo-V2-Flash(nvidia,B 类 TP 跨 Pod,head/worker 形态)head + worker
  - DeepSeek-V4-Pro(ascend,A 类 DP 跨 Pod,head/worker 形态)head + worker

刷新 golden(配方有意变更时):
  UPDATE_GOLDEN=1 PYTHONPATH=src pytest -q tests/integration/test_multi_node_inject_golden.py
然后人工 diff 确认变更符合预期,提交新的 golden/*.sh(显式基线确认)。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from wings_ctl import cli

GOLDEN_DIR = Path(__file__).parent / "golden"


@dataclass(frozen=True)
class InjectScene:
    """一个注入态场景(对应某 Pod 的一次启动)。"""
    golden_file: str
    model_name: str
    model_path: str
    engine: str
    hw_family: str
    device: str
    device_count: int
    rank_ip: str
    node_ips: str = "10.0.0.1,10.0.0.2"
    master_ip: str = "10.0.0.1"
    engine_version: str | None = None  # ascend 需要;nvidia(无版本层)留空
    extra_env: dict = field(default_factory=dict)


SCENES = [
    InjectScene(
        golden_file="inject_mimo_head.sh",
        model_name="MiMo-V2-Flash", model_path="/model/MiMo-V2-Flash",
        engine="vllm", hw_family="gb200", device="nvidia",
        device_count=4, rank_ip="10.0.0.1",
    ),
    InjectScene(
        golden_file="inject_mimo_worker.sh",
        model_name="MiMo-V2-Flash", model_path="/model/MiMo-V2-Flash",
        engine="vllm", hw_family="gb200", device="nvidia",
        device_count=4, rank_ip="10.0.0.2",
    ),
    InjectScene(
        golden_file="inject_dsv4_node0.sh",
        model_name="DeepSeek-V4-Pro", model_path="/model/DeepSeek-V4-Pro",
        engine="vllm-ascend", hw_family="ascend-a3", device="ascend",
        device_count=16, rank_ip="10.0.0.1", engine_version="0.18.0",
    ),
    InjectScene(
        golden_file="inject_dsv4_node1.sh",
        model_name="DeepSeek-V4-Pro", model_path="/model/DeepSeek-V4-Pro",
        engine="vllm-ascend", hw_family="ascend-a3", device="ascend",
        device_count=16, rank_ip="10.0.0.2", engine_version="0.18.0",
    ),
]


def _gen_start_command(scene: InjectScene, config_root: Path, tmp_path: Path,
                       monkeypatch: pytest.MonkeyPatch) -> str:
    """按场景真跑 cli(注入态),返回生成的 start_command.sh(config 绝对路径归一为 <CONFIG>)。"""
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps({
        "hardware_family": scene.hw_family, "device": scene.device, "count": scene.device_count,
    }), encoding="utf-8")
    out_dir = tmp_path / "out"

    for k in ("ENGINE_VERSION", "RANK_IP", "NODE_IPS", "MASTER_IP", "PORT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("RANK_IP", scene.rank_ip)
    monkeypatch.setenv("NODE_IPS", scene.node_ips)
    monkeypatch.setenv("MASTER_IP", scene.master_ip)
    if scene.engine_version:
        monkeypatch.setenv("ENGINE_VERSION", scene.engine_version)
    for k, v in scene.extra_env.items():
        monkeypatch.setenv(k, v)

    monkeypatch.setattr("sys.argv", [
        "wings-ctl", "--engine", scene.engine,
        "--model-name", scene.model_name, "--model-path", scene.model_path,
        "--distributed", "--device-count", str(scene.device_count),
        "--config-root", str(config_root), "--hardware-info", str(hw),
        "--output-dir", str(out_dir),
    ])
    cli.main()

    start = out_dir / "start_command.sh"
    assert start.exists(), f"未生成 start_command.sh:{start}"
    # 归一:把 config 的绝对路径(来源注释里)替换成稳定 token,golden 跨机器可移植。
    return start.read_text(encoding="utf-8").replace(str(config_root), "<CONFIG>")


@pytest.mark.parametrize("scene", SCENES, ids=lambda s: s.golden_file)
def test_multi_node_inject_golden(scene, config_root_real, tmp_path, monkeypatch):
    """注入态逐字 golden:相同输入 → start_command.sh 与 golden 完全一致(防多机回归)。"""
    rendered = _gen_start_command(scene, config_root_real, tmp_path, monkeypatch)
    golden_path = GOLDEN_DIR / scene.golden_file

    if os.environ.get("UPDATE_GOLDEN") == "1":
        golden_path.write_text(rendered, encoding="utf-8")
        pytest.skip(f"UPDATE_GOLDEN:已写入 {scene.golden_file}")

    assert golden_path.exists(), (
        f"缺 golden 文件 {golden_path};首次生成请跑 UPDATE_GOLDEN=1"
    )
    assert rendered == golden_path.read_text(encoding="utf-8"), (
        f"{scene.golden_file} 与 golden 不一致——若为有意变更,UPDATE_GOLDEN=1 刷新并人工 diff 确认"
    )
