"""PD ProcessPlan rendering、audit 与 startup summary 测试。"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from wings_ctl.audit.emitter import emit_audit
from wings_ctl.audit.startup_log import _build_summary_lines
from wings_ctl import cli
from wings_ctl.core.models import (
    ClusterPlacement,
    EngineProcessPlan,
    EngineVersion,
    HardwareContext,
    ParallelShape,
    PdRole,
    ProcessPlan,
    ResolvedConfig,
    ResolvedNode,
    ResolvedPdTopology,
    SystemSetup,
)
from wings_ctl.core.topology import Topology
from wings_ctl.rendering.script_builder import _endpoint_port, _validate_log_analyzer_present, build_scripts


def _resolved(
    process_count: int = 2,
    *,
    engine: str = "vllm",
    system_setup: SystemSetup | None = None,
) -> ResolvedConfig:
    """构造不依赖真实 engine 的 synthetic PD ProcessPlan。"""
    processes = [
        EngineProcessPlan(
            process_index=index,
            local_index=index,
            dp_rank=index,
            visible_devices=(index,),
            advertised_endpoint=f"10.0.0.1:{17000 + index}",
            engine_config_traces={},
            env_traces={},
            argv=["python", "-c", f"raise SystemExit({index + 1})"],
        )
        for index in range(process_count)
    ]
    topology = ResolvedPdTopology(
        input_policy="explicit_allocation",
        role=PdRole.DECODE,
        instance_index=1,
        prefill=ParallelShape(1, 2),
        decode=ParallelShape(process_count, 1),
        dp_size_local=process_count,
        placement=ClusterPlacement(master_ip="10.0.0.1", rank_ip="10.0.0.1", node_ips=["10.0.0.1"]),
        member_index=0,
        rank_start=0,
        rank_end_exclusive=process_count,
    )
    return internal_resolved(topology, processes, process_count, engine=engine, system_setup=system_setup)


def internal_resolved(
    topology: ResolvedPdTopology,
    processes: list,
    process_count: int,
    *,
    engine: str = "vllm",
    system_setup: SystemSetup | None = None,
) -> ResolvedConfig:
    return ResolvedConfig(
        topology=Topology.PD_DECODE,
        hardware=HardwareContext("synthetic", "nvidia"),
        engine=engine,
        engine_version=EngineVersion("1.0.0", "", False, False),
        engine_config_traces={},
        env_traces={},
        source_files=["synthetic.yaml"],
        system_setup=system_setup,
        pd_topology=topology,
        resolution_notes={
            "pd_recipe_recommendation_status": "custom",
            "pd_recipe_shape_match": "false",
            "pd_recipe_role_member_count_match": "true",
        },
        process_plan=ProcessPlan(
            layout="per_local_dp_rank" if process_count > 1 else "single_process",
            lifecycle="fail_together" if process_count > 1 else "single",
            processes=processes,
            endpoints=[process.advertised_endpoint for process in processes],
        ),
    )


def test_pd_fail_together_repro_is_valid_and_propagates_failure(tmp_path: Path) -> None:
    """验证 repro 多进程脚本无部署副作用且任一 child 退出导致整体非零。"""
    _, repro = build_scripts(_resolved(), tmp_path)
    content = repro.read_text(encoding="utf-8")

    syntax = subprocess.run(["bash", "-n", str(repro)], check=False, capture_output=True, text=True)
    executed = subprocess.run(["bash", str(repro)], check=False, capture_output=True, text=True)

    assert syntax.returncode == 0, syntax.stderr
    assert executed.returncode != 0
    assert "Reproducibility Script" in content
    assert "log_analyzer.log_analyzer" not in content
    assert "--progress-file" not in content
    assert "cleanup_analyzer" not in content
    assert "/var/log/wings" not in content


def test_pd_single_process_script_has_log_analyzer(tmp_path: Path) -> None:
    """验证 single_process 注入 log_analyzer，且后台化 + wait（保持 trap 生效）。"""
    start, _ = build_scripts(_resolved(process_count=1), tmp_path)
    content = start.read_text(encoding="utf-8")

    # log_analyzer 进度监控注入
    assert "_wings_log()" in content
    assert "log_analyzer.log_analyzer" in content
    assert "--progress-file" in content
    assert "cleanup_analyzer" in content
    # 后台化 + wait（非 exec 替换 shell），single 不生成多进程 supervisor
    assert "python -c" in content and " &" in content
    assert 'wait "$ENGINE_PID"' in content
    assert "wait -n" not in content


def test_pd_fail_together_script_has_log_analyzer_and_tee(tmp_path: Path) -> None:
    """验证多进程脚本注入 preamble、每条进程 tee 聚合、统一清理含 kill 分析器。"""
    start, _ = build_scripts(_resolved(process_count=2), tmp_path)
    content = start.read_text(encoding="utf-8")

    # log_analyzer 注入
    assert "_wings_log()" in content
    assert "log_analyzer.log_analyzer" in content
    assert "--progress-file" in content
    # 每条进程单独 tee 聚合到 engine.log
    assert content.count("exec > >(tee -a /var/log/wings/engine-full.log") == 2
    # 统一清理(单一 trap)同时终止子进程与 log_analyzer
    assert "kill ${LOG_ANALYZER_PID:-} 2>/dev/null || true" in content
    assert "trap terminate_children EXIT TERM INT" in content
    # 有 pids 收集
    assert 'pids+=("$!")' in content


def test_pd_source_commands_are_rendered_once_before_all_processes(tmp_path: Path, capsys, monkeypatch) -> None:
    """PD source 在父 shell 执行一次，所有 engine 子进程和 dry-run 均可继承。"""
    setup = SystemSetup(commands=["source /dev/null"])
    resolved = _resolved(process_count=2, engine="vllm-ascend", system_setup=setup)
    start, repro = build_scripts(resolved, tmp_path)
    start_content = start.read_text(encoding="utf-8")
    repro_content = repro.read_text(encoding="utf-8")

    hardware_file = tmp_path / "hardware_info.json"
    hardware_file.write_text('{"hardware_family":"synthetic","device":"ascend","count":1}', encoding="utf-8")
    monkeypatch.setattr(cli, "resolve_pipeline", lambda _request: resolved)
    monkeypatch.setattr(cli, "setup_root_logging", lambda: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--engine",
            "vllm-ascend",
            "--model-name",
            "synthetic",
            "--hardware-info",
            str(hardware_file),
            "--dry-run",
        ],
    )
    cli.main()
    preview = capsys.readouterr().out

    assert start_content.count("source /dev/null") == 1
    assert start_content.index("source /dev/null") < start_content.index("python -c")
    assert repro_content.count("source /dev/null") == 1
    assert repro_content.index("source /dev/null") < repro_content.index("exec python -c")
    assert preview.index("source /dev/null") < preview.index("# process[0]")


@pytest.mark.parametrize(
    "endpoint",
    [None, "", "host", "host:abc", "host:0", "host:-1", "host:65536"],
)
def test_pd_endpoint_port_rejects_missing_malformed_or_invalid(endpoint: str | None) -> None:
    """PD endpoint 缺失、格式错误或越界时必须 fail-fast。"""
    with pytest.raises(ValueError):
        _endpoint_port(endpoint)


def test_pd_endpoint_port_accepts_valid_custom_port() -> None:
    assert _endpoint_port("127.0.0.1:17123") == 17123


def test_pd_analyzer_config_backend_port_from_endpoint(tmp_path: Path) -> None:
    """验证 PD analyzer config 的 backend_port 取自 processes[0].advertised_endpoint,
    而非硬编码回退 17000。"""
    # 构造 port=17123 的 synthetic PD 配置
    resolved = _resolved(process_count=1)
    proc = resolved.process_plan.processes[0]
    proc = replace(proc, advertised_endpoint="127.0.0.1:17123")
    plan = replace(resolved.process_plan, processes=[proc], endpoints=["127.0.0.1:17123"])
    resolved = replace(resolved, process_plan=plan)

    start, _ = build_scripts(resolved, tmp_path)
    content = start.read_text(encoding="utf-8")

    assert '"backend_port": 17123' in content
    # 不以此 demo 端口作为兜底触发(确保取的是 endpoint)
    assert '"backend_port": 17000' not in content


def test_validate_log_analyzer_present_pd_raises() -> None:
    """构造缺失拉 log_analyzer 片段的 PD 脚本,断言守卫抛 ValueError。"""
    resolved = _resolved(process_count=1)
    script_without = "#!/usr/bin/env bash\nset -euo pipefail\nexec true\n"

    with pytest.raises(ValueError) as excinfo:
        _validate_log_analyzer_present(resolved, script_without)
    assert "log_analyzer" in str(excinfo.value) or "progress" in str(excinfo.value)


def test_pd_on_guard_failure_no_artifacts_written(monkeypatch, tmp_path: Path) -> None:
    """守卫在落盘前执行:失败时 start_command.sh / repro.sh 均不应存在。"""
    resolved = _resolved(process_count=1)
    # 让守卫必然失败:monkeypatch 让 preamble 返回 None(移除 analyzer 注入),
    # 复用真实 build_scripts 渲染时序;守卫应抛错且不落盘。
    from wings_ctl.rendering import script_builder

    def _no_preamble(_r):
        return None

    monkeypatch.setattr(script_builder, "_build_analyzer_preamble_from_plan", _no_preamble)

    with pytest.raises(ValueError):
        build_scripts(resolved, tmp_path)

    # 落盘前守卫失败,不应留下半成品
    assert not (tmp_path / "start_command.sh").exists()
    assert not (tmp_path / "repro.sh").exists()


def test_validate_log_analyzer_present_pd_passes() -> None:
    """PD 真实脚本含 log_analyzer 片段时,守卫通过。"""
    resolved = _resolved(process_count=1)
    script = (
        "#!/usr/bin/env bash\n"
        "python3 -B -m log_analyzer.log_analyzer --config {}"
        " --log-file /var/log/wings/engine.log --progress-file /shared-volume/progress.jsonl &\n"
        "cleanup_analyzer() { :; }\n"
    )
    # 不抛错即为通过
    _validate_log_analyzer_present(resolved, script)


def test_pd_guard_passes_for_fail_together(tmp_path: Path) -> None:
    """fail_together 脚本含 preamble,三个哨兵齐备,守卫通过。"""
    start, _ = build_scripts(_resolved(process_count=2), tmp_path)
    content = start.read_text(encoding="utf-8")
    # 直接调用守卫验证(不抛错即通过)
    _validate_log_analyzer_present(_resolved(process_count=2), content)


def test_validate_log_analyzer_present_skips_worker() -> None:
    """multi_node worker(index=1)不校验,守卫不抛错。"""
    resolved = _resolved(process_count=1)
    resolved = replace(
        resolved,
        topology=Topology.MULTI_NODE,
        resolution_notes={**resolved.resolution_notes, "multi_node_index": "1"},
    )
    # 即使脚本不含 log_analyzer,worker 也应跳过
    _validate_log_analyzer_present(resolved, "#!/usr/bin/env bash\nexec true\n")


def test_pd_worker_pod_skips_log_analyzer(tmp_path: Path) -> None:
    """跨 pod PD 的 worker Pod(member_index>0)不注入 log_analyzer,守卫也跳过。"""
    # 大 EP:同 role 两个成员 Pod,当前 Pod 为 member 1(worker)
    processes = [
        EngineProcessPlan(
            process_index=0,
            local_index=0,
            dp_rank=2,
            visible_devices=(0,),
            advertised_endpoint=f"10.0.0.2:{17000}",
            engine_config_traces={},
            env_traces={},
            argv=["python", "-c", "raise SystemExit(1)"],
        )
    ]
    topology = ResolvedPdTopology(
        input_policy="explicit_allocation",
        role=PdRole.DECODE,
        instance_index=1,
        prefill=ParallelShape(1, 2),
        decode=ParallelShape(2, 1),
        dp_size_local=1,
        placement=ClusterPlacement(
            master_ip="10.0.0.1", rank_ip="10.0.0.2", node_ips=["10.0.0.1", "10.0.0.2"]
        ),
        member_index=1,
        rank_start=1,
        rank_end_exclusive=2,
    )
    resolved = internal_resolved(topology, processes, 1)

    start, _ = build_scripts(resolved, tmp_path)
    content = start.read_text(encoding="utf-8")
    # worker Pod 不注入 log_analyzer
    assert "log_analyzer.log_analyzer" not in content
    # 守卫对 worker Pod 跳过,不抛错
    _validate_log_analyzer_present(resolved, content)


def test_pd_head_pod_injects_log_analyzer_and_progress_file(tmp_path: Path) -> None:
    """跨 pod PD 的 head Pod(member_index==0)注入 analyzer,进度由 head 代表 Instance。"""
    # 与 worker 测试镜像:同 role 两个成员 Pod,当前 Pod 为 member 0(head)
    processes = [
        EngineProcessPlan(
            process_index=0,
            local_index=0,
            dp_rank=0,
            visible_devices=(0,),
            advertised_endpoint="10.0.0.1:17000",
            engine_config_traces={},
            env_traces={},
            argv=["python", "-c", "raise SystemExit(1)"],
        )
    ]
    topology = ResolvedPdTopology(
        input_policy="explicit_allocation",
        role=PdRole.DECODE,
        instance_index=1,
        prefill=ParallelShape(2, 1),
        decode=ParallelShape(2, 1),
        dp_size_local=1,
        placement=ClusterPlacement(
            master_ip="10.0.0.1", rank_ip="10.0.0.1", node_ips=["10.0.0.1", "10.0.0.2"]
        ),
        member_index=0,
        rank_start=0,
        rank_end_exclusive=1,
    )
    resolved = internal_resolved(topology, processes, 1)

    start, _ = build_scripts(resolved, tmp_path)
    content = start.read_text(encoding="utf-8")
    # head Pod 注入 analyzer 与本 Pod progress.jsonl,语义为"head 代表 Instance"
    assert "log_analyzer.log_analyzer" in content
    assert "--progress-file" in content
    _validate_log_analyzer_present(resolved, content)


def test_validate_log_analyzer_present_skips_placeholder() -> None:
    """multi_node 占位(resolved.nodes 非空)不校验,守卫不抛错。"""
    resolved = _resolved(process_count=1)
    # nodes 非空即占位形态(守卫只判非空,不读字段内容)
    node = ResolvedNode(role="head", index=None, engine_config_traces={}, env_traces={})
    resolved = replace(resolved, nodes=[node])
    _validate_log_analyzer_present(resolved, "#!/usr/bin/env bash\nexit 3\n")


def test_pd_audit_contains_topology_processes_and_maas_boundary(tmp_path: Path) -> None:
    """验证 audit 投影 plan，并明确不可本地观察的 MaaS 全局断言。"""
    audit_path = emit_audit(_resolved(), tmp_path)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))

    assert audit["engine_config"] == {}
    assert audit["pd"]["role"] == "D"
    assert audit["pd"]["local_allocation"]["rank_end_exclusive"] == 2
    assert audit["pd"]["maas_assertions"]["pd_index_unique"] == "maas_asserted_not_locally_observable"
    assert audit["pd"]["maas_assertions"]["peer_role_topology"] == "maas_asserted_not_locally_observable"
    assert audit["pd"]["maas_assertions"]["network_policy"] == "maas_asserted_not_locally_observable"
    assert len(audit["pd"]["process_plan"]["processes"]) == 2
    assert audit["resolution_notes"]["pd_recipe_recommendation_status"] == "custom"


def test_pd_startup_summary_uses_process_plan_values(tmp_path: Path) -> None:
    """验证 startup log 展示 role/index/rank/endpoint/lifecycle，不重复计算。"""
    resolved = _resolved()
    artifacts = {
        "start": tmp_path / "start_command.sh",
        "repro": tmp_path / "repro.sh",
        "audit": tmp_path / "audit.json",
        "output_dir": tmp_path,
        "model_name": "synthetic",
    }

    summary = _build_summary_lines(resolved, artifacts, tmp_path / "wings_start.log")

    assert "pd role=D pd_index=1 member=1/1" in summary
    assert "layout=per_local_dp_rank lifecycle=fail_together" in summary
    assert "ranks=0..1" in summary
    assert "10.0.0.1:17000,10.0.0.1:17001" in summary
    assert "recipe_recommendation status=custom shape_match=false role_member_count_match=true" in summary
