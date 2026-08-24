"""PD ProcessPlan rendering、audit 与 startup summary 测试。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from wings_ctl.audit.emitter import emit_audit
from wings_ctl.audit.startup_log import _build_summary_lines
from wings_ctl.core.models import (
    ClusterPlacement,
    EngineProcessPlan,
    EngineVersion,
    HardwareContext,
    ParallelShape,
    PdRole,
    ProcessPlan,
    ResolvedConfig,
    ResolvedPdTopology,
)
from wings_ctl.core.topology import Topology
from wings_ctl.rendering.script_builder import build_scripts


def _resolved(process_count: int = 2) -> ResolvedConfig:
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
    return ResolvedConfig(
        topology=Topology.PD_DECODE,
        hardware=HardwareContext("synthetic", "nvidia"),
        engine="vllm",
        engine_version=EngineVersion("1.0.0", "", False, False),
        engine_config_traces={},
        env_traces={},
        source_files=["synthetic.yaml"],
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


def test_pd_fail_together_script_is_valid_and_propagates_failure(tmp_path: Path) -> None:
    """验证多进程脚本语法有效，任一 child 退出导致整体非零。"""
    _, repro = build_scripts(_resolved(), tmp_path)

    syntax = subprocess.run(["bash", "-n", str(repro)], check=False, capture_output=True, text=True)
    executed = subprocess.run(["bash", str(repro)], check=False, capture_output=True, text=True)

    assert syntax.returncode == 0, syntax.stderr
    assert executed.returncode != 0


def test_pd_single_process_script_uses_exec(tmp_path: Path) -> None:
    """验证 single_process 保持单命令 exec，不生成 supervisor。"""
    start, _ = build_scripts(_resolved(process_count=1), tmp_path)
    content = start.read_text(encoding="utf-8")

    assert "exec python -c" in content
    assert "wait -n" not in content


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
