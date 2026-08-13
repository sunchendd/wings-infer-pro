"""E2E test — Step 2.1 standalone 最小闭环。

覆盖:
(a) argv 集合等价于 golden 命令
(b) trust_remote_code 来自 default 层 / max_model_len 来自 model 层
(c) 同名参数双层时 events 含两条且取高优先级层
(d) bool=false / None 不出现在 argv
(e) 非 standalone topology raise NotImplementedError
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from wings_ctl.audit.emitter import emit_audit
from wings_ctl.core.config_resolver import MergeLayer, resolve_config, trace_merge
from wings_ctl.core.models import (
    ResolvedConfig,
    ResolvedEnv,
    SourceEvent,
    Target,
    TracedValue,
    UserInput,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.rendering.script_builder import build_scripts


# ─── Golden command (顺序无关) ────────────────────────────────────────────

GOLDEN_ARGV_SET = {
    "vllm",
    "serve",
    "Qwen/Qwen3.5-0.8B",
    "--tensor-parallel-size", "1",
    "--max-model-len", "262144",
    "--reasoning-parser", "qwen3",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--trust-remote-code",
}


def _argv_to_comparable_set(argv: list) -> set:
    """将 argv list 转为 set 用于顺序无关比对。"""
    return set(argv)


# ─── Helpers ──────────────────────────────────────────────────────────────


def _resolve_full(config_root: Path, hardware_info_path: Path) -> ResolvedConfig:
    """执行完整解析链。"""
    os.environ["ENGINE_VERSION"] = "0.19.0"
    try:
        hardware = resolve_hardware(hardware_info_path)
        engine_version = resolve_engine_version(
            config_root, hardware.hardware_family, engine="vllm"
        )
        resolved = resolve_config(
            ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=engine_version),
            Target(model_name="Qwen3.5-0.8B", topology=Topology.STANDALONE, engine="vllm"),
        )
        return resolved
    finally:
        os.environ.pop("ENGINE_VERSION", None)


# ─── Tests ────────────────────────────────────────────────────────────────


class TestStandaloneE2E:
    """端到端 standalone 闭环测试。"""

    def test_a_argv_equals_golden(self, config_root, hardware_info_path):
        """(a) 还原出的 argv 集合等价于目标 golden 命令。"""
        resolved = _resolve_full(config_root, hardware_info_path)
        argv = build_argv(resolved.engine_config_traces)

        assert _argv_to_comparable_set(argv) == GOLDEN_ARGV_SET

    def test_b_trace_layers(self, config_root, hardware_info_path):
        """(b) trust_remote_code/max_model_len 均来自 model 层。"""
        resolved = _resolve_full(config_root, hardware_info_path)

        trc = resolved.engine_config_traces["trust_remote_code"]
        assert trc.final_layer == "model_scenario"
        assert trc.final_value is True

        mml = resolved.engine_config_traces["max_model_len"]
        assert mml.final_layer == "model_scenario"
        assert mml.final_value == 262144

    def test_c_overlapping_key_events(self, config_root, hardware_info_path):
        """(c) 同名参数若同时存在于两层,trace.events 含两条且取高优先级层。"""
        # 两层都有 host
        layer0 = {"host": "127.0.0.1", "port": 9000}
        layer1 = {"host": "0.0.0.0"}

        result = trace_merge([
            MergeLayer("layer_low", layer0, "file_a.yaml", "defaults"),
            MergeLayer("layer_high", layer1, "file_b.yaml", "override"),
        ])

        host_traced = result["host"]
        assert host_traced.final_value == "0.0.0.0"
        assert host_traced.final_layer == "layer_high"
        assert len(host_traced.events) == 2
        assert host_traced.events[0].layer == "layer_low"
        assert host_traced.events[0].action == "set"
        assert host_traced.events[1].layer == "layer_high"
        assert host_traced.events[1].action == "override"

        # port 只在 layer0 → 1 event
        port_traced = result["port"]
        assert port_traced.final_value == 9000
        assert len(port_traced.events) == 1

    def test_d_bool_false_and_none_not_in_argv(self, config_root, hardware_info_path):
        """(d) bool=false / None 值不出现在 argv。"""
        # 构造含 bool=false 和 None 的 traces
        traces = {
            "model": TracedValue(
                final_value="test-model",
                final_layer="test",
                source_file="test.yaml",
                source_path="test.model",
                events=[SourceEvent("set", "test", "test-model", "test.yaml", "test.model")],
            ),
            "some_bool_false": TracedValue(
                final_value=False,
                final_layer="test",
                source_file="test.yaml",
                source_path="test.some_bool_false",
                events=[SourceEvent("set", "test", False, "test.yaml", "test.some_bool_false")],
            ),
            "some_none_param": TracedValue(
                final_value=None,
                final_layer="test",
                source_file="test.yaml",
                source_path="test.some_none_param",
                events=[SourceEvent("set", "test", None, "test.yaml", "test.some_none_param")],
            ),
            "enabled_flag": TracedValue(
                final_value=True,
                final_layer="test",
                source_file="test.yaml",
                source_path="test.enabled_flag",
                events=[SourceEvent("set", "test", True, "test.yaml", "test.enabled_flag")],
            ),
        }

        argv = build_argv(traces)

        assert "vllm" == argv[0]
        assert "serve" == argv[1]
        assert "test-model" == argv[2]
        # bool=true → flag present
        assert "--enabled-flag" in argv
        # bool=false → not present
        assert "--some-bool-false" not in argv
        # None → not present
        assert "--some-none-param" not in argv

    def test_e_non_standalone_raises(self, config_root, hardware_info_path):
        """(e) PD topology 缺规范化 pd_input 时 fail-fast(不再 NotImplementedError)。"""
        os.environ["ENGINE_VERSION"] = "0.19.0"
        try:
            hardware = resolve_hardware(hardware_info_path)
            engine_version = resolve_engine_version(
                config_root, hardware.hardware_family, engine="vllm"
            )

            with pytest.raises(ValueError, match="pd_input"):
                resolve_config(
                    ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=engine_version),
                    Target(model_name="Qwen3.5-0.8B", topology=Topology.PD_PREFILL, engine="vllm"),
                )
        finally:
            os.environ.pop("ENGINE_VERSION", None)

    def test_scripts_generated(self, config_root, hardware_info_path, tmp_path):
        """验证 start_command.sh 和 repro.sh 正确生成。"""
        resolved = _resolve_full(config_root, hardware_info_path)
        start_path, repro_path = build_scripts(resolved, tmp_path)

        assert start_path.exists()
        assert repro_path.exists()

        start_content = start_path.read_text()
        assert "vllm serve" in start_content
        assert "Qwen/Qwen3.5-0.8B" in start_content
        assert "set -euo pipefail" in start_content

        repro_content = repro_path.read_text()
        assert "Engine Command 参数来源" in repro_content
        assert " <- " in repro_content  # 来源注释块
        assert "Reproducibility Script" in repro_content

    def test_generated_scripts_pass_bash_n(self, config_root, hardware_info_path, tmp_path):
        """生成的 start_command.sh/repro.sh 必须通过 bash -n 语法校验。"""
        resolved = _resolve_full(config_root, hardware_info_path)
        start_path, repro_path = build_scripts(resolved, tmp_path)

        subprocess.run(["bash", "-n", str(start_path)], check=True)
        subprocess.run(["bash", "-n", str(repro_path)], check=True)

    def test_generated_scripts_exec_echo_full_command(self, config_root, hardware_info_path, tmp_path):
        """将 exec 替换为 echo 后真实执行,命令必须完整单行输出且参数不丢失。"""
        resolved = _resolve_full(config_root, hardware_info_path)
        start_path, repro_path = build_scripts(resolved, tmp_path)

        def _run_echo(script_path: Path) -> str:
            content = script_path.read_text(encoding="utf-8")
            # 替换引擎命令行为 echo,用于实际执行验证:
            # - start_command.sh: "vllm serve ..." (后台化,行尾有 &)
            # - repro.sh: "exec vllm serve ..." (exec 前缀,需剥离后 echo)
            lines = content.splitlines()
            engine_idx = next(
                (i for i, ln in enumerate(lines)
                 if ln.startswith("vllm serve ") or ln.startswith("exec vllm serve ")),
                -1,
            )
            if engine_idx != -1:
                cmd = lines[engine_idx]
                if cmd.startswith("exec "):
                    cmd = cmd[len("exec "):]
                lines[engine_idx] = "echo " + cmd
            patched = "\n".join(lines) + "\n"
            patched_path = script_path.with_name(f"echo_{script_path.name}")
            patched_path.write_text(patched, encoding="utf-8")
            out = subprocess.run(
                ["bash", str(patched_path)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            return out

        start_out = _run_echo(start_path)
        repro_out = _run_echo(repro_path)

        for out in (start_out, repro_out):
            lines = [line for line in out.splitlines() if line.strip()]
            cmd_lines = [line for line in lines if line.startswith("vllm serve ")]
            assert len(cmd_lines) == 1
            cmd = cmd_lines[0]
            assert "--tensor-parallel-size 1" in cmd
            assert "--max-model-len 262144" in cmd
            assert "--reasoning-parser qwen3" in cmd
            assert "--trust-remote-code" in cmd
            assert cmd.split().count("--") == 0
            assert cmd.count("--") >= 6

    def test_audit_json_generated(self, config_root, hardware_info_path, tmp_path):
        """验证 audit.json 包含完整 events 链。"""
        resolved = _resolve_full(config_root, hardware_info_path)
        audit_path = emit_audit(resolved, tmp_path)

        assert audit_path.exists()
        audit = json.loads(audit_path.read_text())

        # 版本信息
        assert audit["version"]["engine"] == "vllm"
        assert audit["version"]["resolved_config_version"] == "0.19.0"

        # engine_config 每个参数都有 events
        for _, entry in audit["engine_config"].items():
            assert "final_value" in entry
            assert "final_layer" in entry
            assert "events" in entry
            assert len(entry["events"]) >= 1

        # trust_remote_code 的 final_layer 应为 model_scenario
        assert audit["engine_config"]["trust_remote_code"]["final_layer"] == "model_scenario"

    def test_engine_version_fallback(self, config_root, hardware_info_path):
        """验证版本回退时 is_fallback=True + WARNING 审计。"""
        os.environ["ENGINE_VERSION"] = "99.99.99"
        try:
            hardware = resolve_hardware(hardware_info_path)
            engine_version = resolve_engine_version(
                config_root, hardware.hardware_family, engine="vllm"
            )
            assert engine_version.is_fallback is True
            assert engine_version.requested == "99.99.99"
            assert engine_version.resolved == "0.19.0"  # latest available
        finally:
            os.environ.pop("ENGINE_VERSION", None)

    def test_nested_value_serialized_as_json(self):
        """嵌套对象值序列化为紧凑 JSON 字符串。"""
        traces = {
            "model": TracedValue(
                final_value="test-model",
                final_layer="test",
                source_file="t.yaml",
                source_path="t.model",
                events=[SourceEvent("set", "test", "test-model", "t.yaml", "t.model")],
            ),
            "speculative_config": TracedValue(
                final_value={"method": "mtp", "num_speculative_tokens": 3},
                final_layer="test",
                source_file="t.yaml",
                source_path="t.speculative_config",
                events=[SourceEvent("set", "test", {}, "t.yaml", "t.speculative_config")],
            ),
        }

        argv = build_argv(traces)
        assert "--speculative-config" in argv
        idx = argv.index("--speculative-config")
        parsed = json.loads(argv[idx + 1])
        assert parsed == {"method": "mtp", "num_speculative_tokens": 3}

    def test_engine_prefix_vllm(self):
        """engine='vllm' 产出 vllm serve 前缀。"""
        traces = {
            "model": TracedValue(
                final_value="test-model",
                final_layer="test",
                source_file="t.yaml",
                source_path="t.model",
                events=[SourceEvent("set", "test", "test-model", "t.yaml", "t.model")],
            ),
        }
        argv = build_argv(traces, engine="vllm")
        assert argv[:3] == ["vllm", "serve", "test-model"]

    def test_engine_prefix_vllm_ascend(self):
        """engine='vllm-ascend' 也产出 vllm serve 前缀。"""
        traces = {
            "model": TracedValue(
                final_value="test-model",
                final_layer="test",
                source_file="t.yaml",
                source_path="t.model",
                events=[SourceEvent("set", "test", "test-model", "t.yaml", "t.model")],
            ),
        }
        argv = build_argv(traces, engine="vllm-ascend")
        assert argv[:3] == ["vllm", "serve", "test-model"]

    def test_engine_unknown_raises(self):
        """未知 engine 报 ValueError。"""
        traces = {
            "model": TracedValue(
                final_value="test-model",
                final_layer="test",
                source_file="t.yaml",
                source_path="t.model",
                events=[SourceEvent("set", "test", "test-model", "t.yaml", "t.model")],
            ),
        }
        with pytest.raises(ValueError, match="Unknown engine"):
            build_argv(traces, engine="mindie")  # sglang 已支持;用仍未接入的 mindie 验未知引擎报错


# ─── Step 3.2 FeatureOverlay(标准单机:features 块 + 开关)────────────────


def _resolve_with_switches(config_root, hardware_info_path, feature_switches):
    """以 feature_switches 解析 qwen3.5-0.8b(其 features 块仅含 tool_calling)。"""
    os.environ["ENGINE_VERSION"] = "0.19.0"
    try:
        hardware = resolve_hardware(hardware_info_path)
        engine_version = resolve_engine_version(
            config_root, hardware.hardware_family, engine="vllm"
        )
        return resolve_config(
            ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=engine_version),
            Target(model_name="Qwen3.5-0.8B", topology=Topology.STANDALONE, engine="vllm"),
            UserInput(feature_switches=feature_switches),
        )
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def test_feature_overlay_switch_on_injects_args(config_root, hardware_info_path):
    """开 tool 开关 → features.tool_calling 的 args 注入 argv,trace 归 strategy_feature 层。"""
    resolved = _resolve_with_switches(
        config_root, hardware_info_path, {"enable_auto_tool_choice": True}
    )
    tcp = resolved.engine_config_traces["tool_call_parser"]
    assert tcp.final_value == "qwen3_coder"
    assert tcp.final_layer == "strategy_feature"
    assert resolved.engine_config_traces["enable_auto_tool_choice"].final_value is True

    argv = build_argv(resolved.engine_config_traces)
    assert "--tool-call-parser" in argv and "qwen3_coder" in argv
    assert "--enable-auto-tool-choice" in argv


def test_feature_overlay_switch_off_is_noop(config_root, hardware_info_path):
    """不开开关 → features 块不生效,argv 不含 tool_calling 参数(D2:随 model.yaml)。"""
    resolved = _resolve_with_switches(config_root, hardware_info_path, None)
    assert "tool_call_parser" not in resolved.engine_config_traces
    argv = build_argv(resolved.engine_config_traces)
    assert "--tool-call-parser" not in argv
