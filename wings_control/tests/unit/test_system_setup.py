"""Unit tests for system_setup 解析 + 渲染 + audit。"""

from __future__ import annotations

import json

import pytest

from wings_ctl import cli
from wings_ctl.audit.emitter import emit_audit
from wings_ctl.core.models import (
    EngineVersion,
    HardwareContext,
    ResolvedConfig,
    ResolvedNode,
    SystemSetup,
    TracedValue,
    SourceEvent,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.vllm_adapter import build_system_setup_source_commands
from wings_ctl.engines.registry import format_launch_dry_run_preview
from wings_ctl.rendering.script_builder import build_scripts


def _make_minimal_resolved(
    system_setup=None,
    *,
    engine: str = "vllm",
    topology: Topology = Topology.STANDALONE,
) -> ResolvedConfig:
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
        topology=topology,
        hardware=HardwareContext("test-hw", "nvidia", {}),
        engine=engine,
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

    @staticmethod
    def test_multi_node_placeholder_previews_source_commands(tmp_path, capsys, monkeypatch):
        """多机占位产物与 dry-run 均展示尚未执行的节点 source 命令。"""
        setup = SystemSetup(commands=["source /dev/null"])
        resolved = _make_minimal_resolved(engine="vllm-ascend", topology=Topology.MULTI_NODE)
        resolved.nodes = [
            ResolvedNode(
                role="head",
                index=0,
                engine_config_traces=resolved.engine_config_traces,
                env_traces={},
                system_setup=setup,
                source_prefix="scenarios.multi_node.strategies.test.head",
            )
        ]

        start_path, _ = build_scripts(resolved, tmp_path)
        script = start_path.read_text()
        hardware_file = tmp_path / "hardware_info.json"
        hardware_file.write_text('{"hardware_family":"test-hw","device":"ascend","count":1}')
        monkeypatch.setattr(cli, "resolve_pipeline", lambda _request: resolved)
        monkeypatch.setattr(cli, "setup_root_logging", lambda: None)
        monkeypatch.setattr(
            "sys.argv",
            [
                "wings-ctl",
                "--engine",
                "vllm-ascend",
                "--model-name",
                "test-model",
                "--hardware-info",
                str(hardware_file),
                "--dry-run",
            ],
        )
        cli.main()
        preview = capsys.readouterr().out

        assert "#     source /dev/null" in script
        assert preview.index("source /dev/null") < preview.index("vllm serve test-model")

    @staticmethod
    def test_runtime_injected_multi_node_renders_source_commands(tmp_path):
        """已注入的多机节点在 dry-run 和两份可执行脚本中都 source 一次。"""
        setup = SystemSetup(commands=["source /dev/null"])
        resolved = _make_minimal_resolved(
            system_setup=setup,
            engine="vllm-ascend",
            topology=Topology.MULTI_NODE,
        )
        resolved.resolution_notes["multi_node_index"] = "0"

        start_path, repro_path = build_scripts(resolved, tmp_path)
        start_content = start_path.read_text()
        repro_content = repro_path.read_text()
        preview = format_launch_dry_run_preview(resolved)

        assert start_content.index("source /dev/null") < start_content.index("vllm serve test-model")
        assert repro_content.index("source /dev/null") < repro_content.index("exec vllm serve test-model")
        assert preview.index("source /dev/null") < preview.index("vllm serve test-model")

    @staticmethod
    def test_vllm_ascend_source_commands_render_before_engine(tmp_path):
        """vllm-ascend 仅执行受限 source 命令，且位于引擎命令前。"""
        setup = SystemSetup(
            sysctls={},
            sysfs_writes=[],
            commands=[
                "source /usr/local/Ascend/ascend-toolkit/set_env.sh",
                "source /usr/local/Ascend/nnal/atb/set_env.sh",
                "echo must-not-run",
            ],
            source_file="model.yaml",
            source_path="scenarios.standalone.system_setup",
        )
        resolved = _make_minimal_resolved(system_setup=setup, engine="vllm-ascend")
        start_path, repro_path = build_scripts(resolved, tmp_path)
        start_content = start_path.read_text()
        repro_content = repro_path.read_text()

        source_toolkit = "source /usr/local/Ascend/ascend-toolkit/set_env.sh"
        source_atb = "source /usr/local/Ascend/nnal/atb/set_env.sh"
        engine_command = "vllm serve test-model"

        assert source_toolkit in start_content
        assert source_atb in start_content
        assert (
            start_content.index(source_toolkit)
            < start_content.index(source_atb)
            < start_content.index(engine_command)
        )
        assert "echo must-not-run" not in start_content
        assert "2 source entries rendered before engine; 1 entries not rendered" in start_content

        assert source_toolkit in repro_content
        assert source_atb in repro_content
        assert repro_content.index(source_toolkit) < repro_content.index(source_atb) < repro_content.index(
            f"exec {engine_command}"
        )

    @staticmethod
    def test_vllm_ascend_source_command_requires_absolute_path():
        """source 命令拒绝相对路径，避免 recipe 改变工作目录时执行未知文件。"""
        setup = SystemSetup(commands=["source relative/set_env.sh"])

        with pytest.raises(ValueError, match="source <absolute-path>"):
            build_system_setup_source_commands("vllm-ascend", setup)

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
