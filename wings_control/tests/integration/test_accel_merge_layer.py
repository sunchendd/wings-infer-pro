"""建议3 / docs/45 §7:accel.engine_config 作为 ``strategy_accel`` 合并层并入 engine_config_traces。

验证 §7.1 三个坑全闭合(此前 script_builder 末尾 append 的隐患):
- 坑①【优先级反转】→ ``recipe < accel < user_cli``:accel 覆盖 recipe,但 user_cli 覆盖 accel。
- 坑②【同名重复】→ 合并层同名 key 覆盖 → 单一值(不再两个 flag)。
- 坑③【嵌套不深合并】→ 嵌套 dict 走 ``_deep_merge`` 递归(compilation_config 两字段都在)。

accel 侧用 monkeypatch stub(不依赖真 wings-accel 资产;真资产端到端见 test_accel_enabled_e2e)。
"""

from __future__ import annotations

import json
import os

from wings_ctl.accel.smart_accel import AccelResult
from wings_ctl.audit.emitter import emit_audit
from wings_ctl.core import config_resolver
from wings_ctl.core.config_resolver import MergeLayer, resolve_config, trace_merge
from wings_ctl.core.models import ResolvedEnv, Target, UserInput
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.rendering.script_builder import build_scripts


def _resolve_with_accel(config_root, hardware_info_path, monkeypatch, *,
                        accel_engine_config: dict, accel_env: dict | None = None,
                        user_cli: dict | None = None):
    """用 stub accel 跑一遍 resolve_config,返回 ResolvedConfig。

    Args:
        accel_engine_config: stub AccelResult.engine_config(充当 strategy_accel 层)。
        accel_env: stub AccelResult.env(充当 env 的 strategy_accel 层)。
        user_cli: 可选 user_cli 覆盖层(测 accel < user_cli 优先级)。

    Returns:
        resolve_config 的 ResolvedConfig 结果。
    """

    def _stub(**kwargs):
        resolved_accel_env = dict(accel_env or {})
        return AccelResult(
            engine_config=dict(accel_engine_config),
            env=resolved_accel_env,
            enabled=bool(accel_engine_config or resolved_accel_env),
        )

    monkeypatch.setattr(config_resolver, "apply_smart_accel", _stub)
    os.environ["ENGINE_VERSION"] = "0.19.0"
    try:
        hardware = resolve_hardware(hardware_info_path)
        engine_version = resolve_engine_version(config_root, hardware.hardware_family, engine="vllm")
        return resolve_config(
            ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=engine_version),
            Target(model_name="Qwen3.5-0.8B", topology=Topology.STANDALONE, engine="vllm"),
            UserInput(cli_overrides=user_cli),
        )
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def test_accel_layer_lands_in_traces_as_strategy_accel(config_root, hardware_info_path, monkeypatch):
    """accel 专用参数(recipe 里没有)→ 进 traces,final_layer=strategy_accel,值来自 accel。"""
    resolved = _resolve_with_accel(
        config_root, hardware_info_path, monkeypatch,
        accel_engine_config={"speculative_config": {"method": "mtp"}},
    )
    spec = resolved.engine_config_traces["speculative_config"]
    assert spec.final_layer == "strategy_accel"
    assert spec.final_value == {"method": "mtp"}
    assert spec.source_file == "<wings-accel>"


def test_accel_overrides_recipe(config_root, hardware_info_path, monkeypatch):
    """坑①下半:recipe < accel —— accel 同名值覆盖 recipe(max_model_len 262144 → 999)。"""
    resolved = _resolve_with_accel(
        config_root, hardware_info_path, monkeypatch,
        accel_engine_config={"max_model_len": 999},
    )
    mml = resolved.engine_config_traces["max_model_len"]
    assert mml.final_layer == "strategy_accel"
    assert mml.final_value == 999


def test_user_cli_overrides_accel(config_root, hardware_info_path, monkeypatch):
    """坑①上半:accel < user_cli —— 用户显式值最高,盖过 accel(999 → 111)。"""
    resolved = _resolve_with_accel(
        config_root, hardware_info_path, monkeypatch,
        accel_engine_config={"max_model_len": 999},
        user_cli={"max_model_len": 111},
    )
    mml = resolved.engine_config_traces["max_model_len"]
    assert mml.final_layer == "user_cli"
    assert mml.final_value == 111


def test_empty_accel_layer_is_noop(config_root, hardware_info_path, monkeypatch):
    """空 accel 产出 → strategy_accel 层为空 dict → traces 无变化(recipe 值原样,零影响)。"""
    resolved = _resolve_with_accel(
        config_root, hardware_info_path, monkeypatch, accel_engine_config={},
    )
    mml = resolved.engine_config_traces["max_model_len"]
    assert mml.final_layer == "model_scenario"          # 未被 accel 触碰
    assert "strategy_accel" not in {ev.layer for tv in resolved.engine_config_traces.values() for ev in tv.events}


def test_accel_deep_merges_nested_with_recipe():
    """坑②③:accel 与 recipe 同名嵌套 dict → 深合并成【单一】key,两字段都在(非两个 flag)。"""
    merged = trace_merge([
        # recipe 层:model_scenario
        MergeLayer("model_scenario", {"compilation_config": {"mode": 0}},
                   "model.yaml", "scenarios.standalone.engine_config"),
        # accel 层:strategy_accel
        MergeLayer("strategy_accel", {"compilation_config": {"cudagraph_mode": "FULL_DECODE_ONLY"}},
                   "<wings-accel>", "strategy.accel"),
    ])
    cc = merged["compilation_config"]
    assert cc.final_value == {"mode": 0, "cudagraph_mode": "FULL_DECODE_ONLY"}  # 深合并:两字段都保留
    assert cc.final_layer == "strategy_accel"
    assert len(merged) == 1                                                # 单一 key,不重复


def test_accel_env_overrides_existing_env_once(config_root, hardware_info_path, monkeypatch, tmp_path):
    """验证 accel env 覆盖 recipe env，保留事件链且脚本只导出最终值一次。"""
    original_select_scenario = config_resolver._select_scenario

    def _select_with_recipe_env(*args, **kwargs):
        """在既有 fixture 场景中注入一个待覆盖的 recipe 环境变量。"""
        scenario = original_select_scenario(*args, **kwargs)
        if scenario.get("nodes"):
            return scenario
        return {**scenario, "env": {**scenario["env"], "WINGS_ACCEL_KV": "recipe"}}

    monkeypatch.setattr(config_resolver, "_select_scenario", _select_with_recipe_env)

    resolved = _resolve_with_accel(
        config_root,
        hardware_info_path,
        monkeypatch,
        accel_engine_config={},
        accel_env={"WINGS_ACCEL_KV": "accel"},
    )
    traced = resolved.env_traces["WINGS_ACCEL_KV"]
    assert traced.final_layer == "strategy_accel"
    assert traced.final_value == "accel"
    assert traced.source_file == "<wings-accel>"
    assert traced.source_path == "strategy.accel.env.WINGS_ACCEL_KV"
    assert [event.layer for event in traced.events] == ["model_scenario", "strategy_accel"]
    assert [event.action for event in traced.events] == ["set", "override"]

    start_path, repro_path = build_scripts(resolved, tmp_path)
    start_text = start_path.read_text(encoding="utf-8")
    repro_text = repro_path.read_text(encoding="utf-8")
    assert start_text.count("export WINGS_ACCEL_KV=accel") == 1
    assert repro_text.count("export WINGS_ACCEL_KV=accel") == 1
    assert "Environment Variables (wings-accel)" not in repro_text

    audit_path = emit_audit(resolved, tmp_path)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audited = audit["env"]["WINGS_ACCEL_KV"]
    assert audited["final_value"] == "accel"
    assert [event["layer"] for event in audited["events"]] == ["model_scenario", "strategy_accel"]
