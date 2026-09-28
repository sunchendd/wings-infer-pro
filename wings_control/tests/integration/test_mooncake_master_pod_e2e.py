"""Mooncake master 专属 Pod CLI 入口端到端回归(修复:master Pod 缺 MASTER_IP 不再被拦)。

背景(见 /home/tjl/wings/doc/mooncake_master_pod_entry_fix.md):双节点分布式部署 +
分布式 KV 卸载时,MaaS 额外创建 master 专属 Pod(注入 IS_MOONCAKE_MASTER,不下发
推理集群三件套 RANK_IP/NODE_IPS/MASTER_IP),并以与 engine Pod 相同的参数调用
wings_start.sh --distributed。修复前 pre_template 在 CLI 入口即抛
"Distributed mode (--distributed) requires MASTER_IP in the environment";
修复后 master Pod 走完整 CLI → resolve → build_scripts,由交付支线产出 master 脚本。

覆盖:
1. master Pod(无三件套 + 特性未开)→ CLI 成功,产物为挂起兜底交付(非占位脚本,
   无 install.py / log_analyzer / 引擎命令);
2. 非 master Pod 同输入 → 既有 fail-fast 原样保留(SystemExit 2 + 原错误信息)。
"""

from __future__ import annotations

import json

import pytest

from wings_ctl import cli

_CLUSTER_ENV = ("RANK_IP", "NODE_IPS", "MASTER_IP", "IS_MOONCAKE_MASTER",
                "ENABLE_DISTRIBUTED_KV_OFFLOAD", "ENABLE_KV_OFFLOAD")


def _run_cli(tmp_path, monkeypatch, config_root) -> None:
    """以双节点部署的同一套参数真跑 cli.main()(master/engine Pod 唯一差异是 env)。"""
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps({
        "hardware_family": "gb200", "device": "nvidia", "count": 4,
    }), encoding="utf-8")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl", "--engine", "vllm",
            "--model-name", "MiMo-V2-Flash", "--model-path", "/model/MiMo-V2-Flash",
            "--distributed", "--device-count", "4",
            "--config-root", str(config_root), "--hardware-info", str(hw),
            "--output-dir", str(out_dir),
        ],
    )
    cli.main()


def test_mooncake_master_pod_without_cluster_env_survives_entry_gate(
    config_root_real, tmp_path, monkeypatch, capsys
):
    """master Pod 缺 MASTER_IP:不再在 pre_template 报错;交付为挂起兜底脚本。"""
    for k in _CLUSTER_ENV:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("IS_MOONCAKE_MASTER", "true")
    # 特性未开(无 ENABLE_DISTRIBUTED_KV_OFFLOAD)→ master 分支段不产出 → hold 段。
    monkeypatch.setattr(
        "wings_ctl.common.settings.settings.ADVANCED_FEATURES_FILE",
        str(tmp_path / "advanced_features.json"),
    )

    _run_cli(tmp_path, monkeypatch, config_root_real)  # 修复前此处 SystemExit 2

    start = (tmp_path / "out" / "start_command.sh")
    assert start.exists(), "master Pod 必须照常产出 start_command.sh"
    text = start.read_text(encoding="utf-8")
    # 不是 multi_node 占位脚本(exit 3 / 横幅),是 master 专属交付
    assert "MULTI-NODE — RUNTIME INJECTION PENDING" not in text
    assert "exit 3" not in text
    assert "distributed KV offload is NOT effective" in text  # 特性未开 → 挂起兜底段
    assert "while true; do sleep 3600; done" in text
    # master Pod 在任何情况下都不承担推理职责:无 install 段 / 分析器 / 引擎命令
    assert "install.py" not in text
    assert "log_analyzer" not in text
    engine_lines = [ln for ln in text.splitlines() if ln.lstrip().startswith("vllm serve")]
    assert not engine_lines


def test_non_master_pod_without_cluster_env_keeps_fail_fast(
    config_root_real, tmp_path, monkeypatch, capsys
):
    """普通 Pod(无 IS_MOONCAKE_MASTER)+ --distributed + 缺 MASTER_IP → 既有 fail-fast 原样。"""
    for k in _CLUSTER_ENV:
        monkeypatch.delenv(k, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        _run_cli(tmp_path, monkeypatch, config_root_real)

    assert excinfo.value.code == 2
    assert "requires MASTER_IP" in capsys.readouterr().err
