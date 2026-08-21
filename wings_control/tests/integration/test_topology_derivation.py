"""大策略层 topology 判定(Phase2)CLI 集成测试。

验证 topology 由 `--distributed`(CLI)+ `PD_ROLE`/`MASTER_IP`(env)推导,且 `--topology`
已删:无 flag→standalone;`--distributed` 缺 MASTER_IP→友好报错;有→multi_node(已实现,
recipe 缺 multi_node 场景时友好报错);`PD_ROLE`→PD 预留,友好报错。所有"未支持/未找到"
均在 cli 边界转友好 SystemExit,不抛 traceback。对应 strategy/pre_template.py + cli.main 接线。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wings_ctl import cli


def _argv(config_root_real: Path, tmp_path: Path, *extra: str) -> list[str]:
    """构造一条 dry-run CLI argv(vllm-ascend/DeepSeek-V4-Flash),`extra` 追加额外 flag。"""
    hw = tmp_path / "hw.json"
    hw.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    return [
        "wings-ctl", "--engine", "vllm-ascend",
        "--model-name", "DeepSeek-V4-Flash",  # 模型名称(配方标识 + served);--model 已删
        "--config-root", str(config_root_real), "--hardware-info", str(hw),
        "--dry-run", *extra,
    ]


def test_no_distributed_derives_standalone(config_root_real, tmp_path, monkeypatch, capsys):
    """无 --distributed → 推导 standalone,正常产出 argv(不抛异常)。"""
    monkeypatch.setenv("ENGINE_VERSION", "v0.18.0")
    monkeypatch.setattr("sys.argv", _argv(config_root_real, tmp_path))
    cli.main()  # 不抛异常
    assert "vllm serve" in capsys.readouterr().out


def test_distributed_missing_master_ip_friendly_error(config_root_real, tmp_path, monkeypatch, capsys):
    """--distributed 缺 MASTER_IP → 友好报错(SystemExit 2 + stderr 含 MASTER_IP)。"""
    monkeypatch.setenv("ENGINE_VERSION", "v0.18.0")
    monkeypatch.delenv("MASTER_IP", raising=False)
    monkeypatch.setattr("sys.argv", _argv(config_root_real, tmp_path, "--distributed"))
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "MASTER_IP" in capsys.readouterr().err


def test_distributed_with_master_ip_recipe_without_multi_node_friendly_error(
    config_root_real, tmp_path, monkeypatch, capsys
):
    """--distributed + MASTER_IP → multi_node;DeepSeek-V4-Flash recipe 无 multi_node 场景

    → 友好报错(SystemExit 2),不抛 NotImplementedError traceback(multi_node 本身已实现,
    缺的是该 recipe 的 multi_node 场景)。
    """
    monkeypatch.setenv("ENGINE_VERSION", "v0.18.0")
    monkeypatch.setenv("MASTER_IP", "10.0.0.1")
    monkeypatch.setattr("sys.argv", _argv(config_root_real, tmp_path, "--distributed"))
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "multi_node" in capsys.readouterr().err


def test_pd_role_is_reserved_friendly_error(config_root_real, tmp_path, monkeypatch, capsys):
    """PD_ROLE 置位 → PD 分离为预留点(本期不实现)→ 友好报错(SystemExit 2),不抛 traceback。"""
    monkeypatch.setenv("ENGINE_VERSION", "v0.18.0")
    monkeypatch.setenv("PD_ROLE", "P")
    monkeypatch.setattr("sys.argv", _argv(config_root_real, tmp_path))
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "PD" in capsys.readouterr().err
