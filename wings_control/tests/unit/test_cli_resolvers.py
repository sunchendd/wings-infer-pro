"""cli 小工具 + 错误/分支负路径单测(补覆盖:_resolve_model_name / _resolve_device_count / dry-run 多节点)。"""

from __future__ import annotations

import json
import logging

import pytest

from wings_ctl import cli


# ─── _resolve_model_name(配方标识推导)──────────────────────────────────────

def test_resolve_model_name_explicit():
    """显式 --model-name 优先。"""
    assert cli._resolve_model_name("Qwen3.5-9B", None) == "Qwen3.5-9B"


def test_resolve_model_name_from_path_basename():
    """缺 --model-name → 取 --model-path 的 basename。"""
    assert cli._resolve_model_name(None, "/weights/MiniMax-M3-MXFP8") == "MiniMax-M3-MXFP8"


def test_resolve_model_name_both_none_raises():
    """两者皆缺 → ValueError(无法确定配方)。"""
    with pytest.raises(ValueError, match="model-name|model-path"):
        cli._resolve_model_name(None, None)


# ─── _resolve_device_count(卡数:CLI > env > None)────────────────────────────

def test_resolve_device_count_cli_wins(monkeypatch):
    """CLI 值优先于 DEVICE_COUNT env。"""
    monkeypatch.setenv("DEVICE_COUNT", "4")
    assert cli._resolve_device_count(8) == 8


def test_resolve_device_count_from_env(monkeypatch):
    """缺 CLI → 取 DEVICE_COUNT env。"""
    monkeypatch.setenv("DEVICE_COUNT", "16")
    assert cli._resolve_device_count(None) == 16


def test_resolve_device_count_invalid_env_ignored(monkeypatch):
    """DEVICE_COUNT 非整数 → 忽略(按 unset 处理,warn)。"""
    monkeypatch.setenv("DEVICE_COUNT", "notint")
    assert cli._resolve_device_count(None) is None


def test_resolve_device_count_unset(monkeypatch):
    """无 CLI、无 env → None。"""
    monkeypatch.delenv("DEVICE_COUNT", raising=False)
    assert cli._resolve_device_count(None) is None


# ─── _resolve_engine / _canonicalize_engine(引擎名归一:下划线→连字符)──────────

def test_canonicalize_engine_underscore_to_hyphen():
    """下划线形式归一到 config 目录命名(vllm_ascend → vllm-ascend)。"""
    assert cli._canonicalize_engine("vllm_ascend") == "vllm-ascend"


def test_canonicalize_engine_hyphen_and_plain_unchanged():
    """已是连字符 / 单词形式不变(vllm-ascend / vllm 原样)。"""
    assert cli._canonicalize_engine("vllm-ascend") == "vllm-ascend"
    assert cli._canonicalize_engine("  vllm  ") == "vllm"


def test_resolve_engine_cli_underscore_canonicalized():
    """CLI --engine vllm_ascend 归一为 vllm-ascend(部署下划线入参兼容)。"""
    assert cli._resolve_engine("vllm_ascend") == "vllm-ascend"


def test_resolve_engine_env_underscore_canonicalized(monkeypatch):
    """缺 CLI → ENGINE env 的下划线形式同样归一。"""
    monkeypatch.setenv("ENGINE", "vllm_ascend")
    assert cli._resolve_engine(None) == "vllm-ascend"


# ─── _derive_max_model_len(input+output → max_model_len)──────────────────────

def test_derive_max_model_len_sum():
    """两者都给 → max_model_len = input + output(无余量)。"""
    assert cli._derive_max_model_len(4096, 1024) == 5120


def test_derive_max_model_len_missing_returns_none():
    """任一缺失 → None(不派生,不覆盖 recipe)。"""
    assert cli._derive_max_model_len(None, 1024) is None
    assert cli._derive_max_model_len(4096, None) is None


def test_derive_max_model_len_nonpositive_returns_none():
    """含非正值 → None(跳过派生,warn)。"""
    assert cli._derive_max_model_len(0, 1024) is None
    assert cli._derive_max_model_len(4096, -1) is None


def test_collect_overrides_injects_max_model_len():
    """收集层:给 input/output → overrides 注入 max_model_len(供 user_cli 覆盖 recipe)。"""
    ov = cli._collect_user_cli_overrides(
        host=None, port=None, model_path=None, input_length=4096, output_length=4096
    )
    assert ov["max_model_len"] == 8192


# ─── --trust-remote-code 不传 → 告警(MaaS v3:选填但告警)────────────────────

def _argv_qwen_dryrun(config_root, hw, *extra):
    """legacy 夹具 Qwen3.5-0.8B 的最小 standalone dry-run argv;extra 追加额外 flag。"""
    return ["wings-ctl", "--engine", "vllm", "--model-name", "Qwen3.5-0.8B",
            "--model-path", "/m/Qwen3.5-0.8B", "--config-root", str(config_root),
            "--hardware-info", str(hw), "--dry-run", *extra]


def test_main_warns_when_no_trust_remote_code(config_root, tmp_path, monkeypatch, caplog):
    """不传 --trust-remote-code → 打 WARNING(不阻断,仍正常 dry-run)。"""
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps({"hardware_family": "nvidia-RTX5880", "device": "nvidia", "count": 1}))
    monkeypatch.setenv("ENGINE_VERSION", "0.19.0")
    monkeypatch.setattr("sys.argv", _argv_qwen_dryrun(config_root, hw))
    with caplog.at_level(logging.WARNING):
        cli.main()
    assert any("trust-remote-code" in r.message for r in caplog.records)


def test_main_no_warn_when_trust_remote_code_passed(config_root, tmp_path, monkeypatch, caplog):
    """传了 --trust-remote-code → 不打该 WARNING。"""
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps({"hardware_family": "nvidia-RTX5880", "device": "nvidia", "count": 1}))
    monkeypatch.setenv("ENGINE_VERSION", "0.19.0")
    monkeypatch.setattr("sys.argv", _argv_qwen_dryrun(config_root, hw, "--trust-remote-code"))
    with caplog.at_level(logging.WARNING):
        cli.main()
    assert not any("trust-remote-code" in r.message for r in caplog.records)


def test_main_accepts_and_logs_v3_subsystem_switches(config_root, tmp_path, monkeypatch, caplog):
    """v3 子系统开关(--enable-rag-acc/smartqos/otlp-traces)被接收不崩 + 日志留痕(暂仅保存)。"""
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps({"hardware_family": "nvidia-RTX5880", "device": "nvidia", "count": 1}))
    monkeypatch.setenv("ENGINE_VERSION", "0.19.0")
    monkeypatch.setattr(
        "sys.argv",
        _argv_qwen_dryrun(config_root, hw, "--enable-smartqos", "--enable-otlp-traces", "--enable-rag-acc"),
    )
    with caplog.at_level(logging.INFO):
        cli.main()  # 不应抛 SystemExit(unrecognized arguments)
    assert any("已接收子系统特性开关" in r.message for r in caplog.records)


# ─── main() 错误路径 + dry-run 多节点占位分支 ────────────────────────────────

def test_main_missing_model_name_and_path_friendly_error(config_root_real, tmp_path, monkeypatch, capsys):
    """既无 --model-name 又无 --model-path → parser.error(exit 2,友好,无 traceback)。"""
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps({"hardware_family": "gb200", "device": "nvidia", "count": 8}))
    monkeypatch.setattr(
        "sys.argv",
        ["wings-ctl", "--engine", "vllm", "--config-root", str(config_root_real),
         "--hardware-info", str(hw), "--dry-run"],
    )
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2


def test_dry_run_multi_node_placeholder_prints_nodes(config_root_real, tmp_path, monkeypatch, capsys):
    """multi_node 无运行时上下文(3.1-b)→ dry-run 逐节点打印占位 argv(覆盖 cli resolved.nodes 分支)。"""
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps({"hardware_family": "gb200", "device": "nvidia", "count": 8}))
    monkeypatch.delenv("RANK_IP", raising=False)
    monkeypatch.delenv("NODE_IPS", raising=False)
    monkeypatch.setenv("MASTER_IP", "10.0.0.1")  # 分布式必填(无 RANK_IP/NODE_IPS → 占位)
    monkeypatch.setattr(
        "sys.argv",
        ["wings-ctl", "--engine", "vllm", "--model-name", "MiMo-V2-Flash",
         "--model-path", "/model/MiMo-V2-Flash", "--distributed",
         "--config-root", str(config_root_real), "--hardware-info", str(hw), "--dry-run"],
    )
    cli.main()
    out = capsys.readouterr().out
    assert "node[" in out  # 逐节点占位打印
