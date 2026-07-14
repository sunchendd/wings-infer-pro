"""Unit tests for system_setup 解析 + 渲染 + audit。"""

from __future__ import annotations

import json

from wings_ctl.audit.emitter import emit_audit
from wings_ctl.core.models import (
    EngineVersion,
    HardwareContext,
    ResolvedConfig,
    SystemSetup,
    TracedValue,
    SourceEvent,
)
from wings_ctl.core.topology import Topology
from wings_ctl.rendering.script_builder import build_scripts


def _make_minimal_resolved(system_setup=None) -> ResolvedConfig:
    """构造最小 ResolvedConfig 用于测试。"""
    traces = {
        "model": TracedValue(
            final_value="test-model",
            final_layer="model_scenario",
            source_file="model.yaml",
            source_path="scenarios.standalone.engine_config.model",
            events=[SourceEvent("set", "model_scenario", "test-model", "model.yaml",
                                "scenarios.standalone.engine_config.model")],
        ),
        "trust_remote_code": TracedValue(
            final_value=True,
            final_layer="model_scenario",
            source_file="model.yaml",
            source_path="scenarios.standalone.engine_config.trust_remote_code",
            events=[SourceEvent("set", "model_scenario", True, "model.yaml",
                                "scenarios.standalone.engine_config.trust_remote_code")],
        ),
    }
    return ResolvedConfig(
        topology=Topology.STANDALONE,
        hardware=HardwareContext("test-hw", "nvidia", {}),
        engine="vllm",
        engine_version=EngineVersion(requested="0.19.0", resolved="0.19.0", is_fallback=False),
        engine_config_traces=traces,
        env_traces={},
        source_files=["model.yaml"],
        system_setup=system_setup,
    )


class TestSystemSetupParsing:
    """system_setup 解析到 ResolvedConfig 的测试。"""

    def test_system_setup_none_when_absent(self):
        """场景无 system_setup 时 ResolvedConfig.system_setup 为 None。"""
        resolved = _make_minimal_resolved(system_setup=None)
        assert resolved.system_setup is None

    def test_system_setup_populated(self):
        """system_setup 正确填充 sysctls/sysfs_writes/commands。"""
        setup = SystemSetup(
            sysctls={"vm.swappiness": 0, "kernel.numa_balancing": 0},
            sysfs_writes=[{"path": "/sys/devices/test", "value": "performance"}],
            commands=["echo hello"],
            source_file="Kimi-K2.5.yaml",
            source_path="scenarios.standalone.system_setup",
        )
        resolved = _make_minimal_resolved(system_setup=setup)
        assert resolved.system_setup is not None
        assert resolved.system_setup.sysctls == {"vm.swappiness": 0, "kernel.numa_balancing": 0}
        assert len(resolved.system_setup.sysfs_writes) == 1
        assert resolved.system_setup.commands == ["echo hello"]


class TestSystemSetupRendering:
    """system_setup 在 start_command.sh 中以注释形式渲染。"""

    def test_sysctls_rendered_as_comments(self, tmp_path):
        """sysctls 渲染为注释行。"""
        setup = SystemSetup(
            sysctls={"vm.swappiness": 0, "kernel.numa_balancing": 0},
            sysfs_writes=[],
            commands=[],
            source_file="model.yaml",
            source_path="scenarios.standalone.system_setup",
        )
        resolved = _make_minimal_resolved(system_setup=setup)
        start_path, _ = build_scripts(resolved, tmp_path)
        content = start_path.read_text()

        assert "# sysctls:" in content
        assert "#   sysctl -w vm.swappiness=0" in content
        assert "#   sysctl -w kernel.numa_balancing=0" in content

    def test_sysfs_writes_rendered_as_comments(self, tmp_path):
        """sysfs_writes 渲染为注释行。"""
        setup = SystemSetup(
            sysctls={},
            sysfs_writes=[
                {"path": "/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor",
                 "value": "performance"},
            ],
            commands=[],
            source_file="model.yaml",
            source_path="scenarios.standalone.system_setup",
        )
        resolved = _make_minimal_resolved(system_setup=setup)
        start_path, _ = build_scripts(resolved, tmp_path)
        content = start_path.read_text()

        assert "# sysfs_writes:" in content
        assert "performance" in content
        assert "scaling_governor" in content

    def test_commands_noted_but_not_rendered(self, tmp_path):
        """commands 标注存在但不渲染为可执行行。"""
        setup = SystemSetup(
            sysctls={},
            sysfs_writes=[],
            commands=["nic_name=eth0", "local_ip=10.0.0.1"],
            source_file="model.yaml",
            source_path="scenarios.standalone.system_setup",
        )
        resolved = _make_minimal_resolved(system_setup=setup)
        start_path, _ = build_scripts(resolved, tmp_path)
        content = start_path.read_text()

        assert "commands (2 entries, not rendered)" in content
        # 确保 commands 内容不以可执行行出现
        assert "nic_name=eth0" not in content.replace("# commands", "")

    def test_no_system_setup_no_section(self, tmp_path):
        """无 system_setup 时脚本不含 System Setup 段。"""
        resolved = _make_minimal_resolved(system_setup=None)
        start_path, _ = build_scripts(resolved, tmp_path)
        content = start_path.read_text()

        assert "System Setup" not in content

    def test_source_annotation_in_comments(self, tmp_path):
        """注释中包含 source 信息。"""
        setup = SystemSetup(
            sysctls={"vm.swappiness": 0},
            sysfs_writes=[],
            commands=[],
            source_file="Kimi-K2.5.yaml",
            source_path="scenarios.standalone.system_setup",
        )
        resolved = _make_minimal_resolved(system_setup=setup)
        start_path, _ = build_scripts(resolved, tmp_path)
        content = start_path.read_text()

        assert "Kimi-K2.5.yaml" in content
        assert "scenarios.standalone.system_setup" in content


class TestSystemSetupAudit:
    """system_setup 在 audit.json 中的记录。"""

    def test_audit_contains_system_setup(self, tmp_path):
        """audit.json 含 system_setup 块。"""
        setup = SystemSetup(
            sysctls={"vm.swappiness": 0},
            sysfs_writes=[{"path": "/sys/test", "value": "1"}],
            commands=["cmd1"],
            source_file="model.yaml",
            source_path="scenarios.standalone.system_setup",
        )
        resolved = _make_minimal_resolved(system_setup=setup)
        audit_path = emit_audit(resolved, tmp_path)
        audit = json.loads(audit_path.read_text())

        assert "system_setup" in audit
        assert audit["system_setup"]["sysctls"] == {"vm.swappiness": 0}
        assert audit["system_setup"]["sysfs_writes"] == [{"path": "/sys/test", "value": "1"}]
        assert audit["system_setup"]["commands"] == ["cmd1"]
        assert audit["system_setup"]["source_file"] == "model.yaml"
        assert audit["system_setup"]["source_path"] == "scenarios.standalone.system_setup"

    def test_audit_no_system_setup_when_absent(self, tmp_path):
        """无 system_setup 时 audit.json 不含该块。"""
        resolved = _make_minimal_resolved(system_setup=None)
        audit_path = emit_audit(resolved, tmp_path)
        audit = json.loads(audit_path.read_text())

        assert "system_setup" not in audit
