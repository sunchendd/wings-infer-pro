"""PD exact recipe E2E — resolve_pipeline → ProcessPlan → scripts/audit 全链。

用 tmp 内 synthetic 配置资产(不污染 config/)，验证 strict version/model 选择、
P/D pair、rank/设备/endpoint 展开、structured argv 与 audit 投影。
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest
import yaml

from wings_ctl import cli
from wings_ctl.core.models import (
    ClusterPlacement,
    ExplicitPdTopology,
    ParallelShape,
    PdRole,
    PdRuntimeInput,
    PipelineRequest,
    Target,
    UserInput,
)
from wings_ctl.core.topology import Topology
from wings_ctl.pipeline import resolve_pipeline, run_pipeline

_VARIANT = "Synthetic-GLM51-FP8"
_ORDINARY_VARIANT = "Synthetic-Ordinary-PD"


def _write_hardware(root: Path) -> Path:
    """写 hardware_info.json。"""
    path = root / "hardware_info.json"
    path.write_text(
        json.dumps(
            {
                "hardware_family": "ascend-a3",
                "device": "ascend",
                "gpu": "910B",
            }
        ),
        encoding="utf-8",
    )
    return path


def _engine_config(role: str) -> dict:
    """构造 role-specific synthetic engine_config。"""
    kv_role = "kv_producer" if role == "P" else "kv_consumer"
    return {
        "model": "synthetic/glm51",
        "port": "$2",
        "data_parallel_size": "$3",
        "data_parallel_rank": "$4",
        "data_parallel_address": "$5",
        "data_parallel_rpc_port": 12890 if role == "P" else 12777,
        "tensor_parallel_size": "$7",
        "max_model_len": 65536,
        "kv_transfer_config": {
            "kv_connector": "MooncakeConnectorV1",
            "kv_role": kv_role,
            "kv_port": 36000 if role == "P" else 36100,
            "kv_connector_extra_config": {
                "prefill": {"dp_size": 4, "tp_size": 8},
                "decode": {"dp_size": 4, "tp_size": 1},
            },
        },
    }


def _write_model_root(root: Path) -> None:
    """写 engines/vllm-ascend/v0.23.0/ascend-a3/models 下的 exact variant。"""
    models = root / "engines" / "vllm-ascend" / "v0.23.0" / "ascend-a3" / "models" / "Synthetic"
    models.mkdir(parents=True, exist_ok=True)
    nodes = []
    for role, role_name in (("P", "prefill"), ("D", "decode")):
        for index in range(2):
            nodes.append(
                {
                    "role": role_name,
                    "index": index,
                    "engine_config": _engine_config(role),
                    "env": {
                        "SYNTHETIC_ROLE": role,
                        "HCCL_IF_IP": "$local_ip",
                        "GLOO_SOCKET_IFNAME": "$nic_name",
                        "TP_SOCKET_IFNAME": "$nic_name",
                        "HCCL_SOCKET_IFNAME": "$nic_name",
                    },
                    "system_setup": {"commands": ["echo must-not-run"]},
                }
            )
    payload = {
        "schema_version": "synthetic",
        "model": {"name": "Synthetic-GLM", "variant_name": _VARIANT},
        "features": {
            "tool_calling": {
                "args": [
                    "--enable-auto-tool-choice",
                    "--tool-call-parser",
                    "synthetic_tool",
                    "--tokenizer-mode",
                    "synthetic",
                ]
            },
            "reasoning": {"args": ["--reasoning-parser", "synthetic_reasoning"]},
            "spec_decoding": {
                "args": [
                    "--speculative-config",
                    '{"method":"mtp","num_speculative_tokens":1}',
                ]
            },
        },
        "scenarios": {
            "pd_disaggregation": {
                "strategies": {
                    "approved": {
                        "default_strategy": True,
                        "nodes": nodes,
                    }
                }
            }
        },
    }
    (models / "glm51-fp8.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _write_ordinary_model_root(root: Path) -> None:
    """写 DP1 普通 PD exact recipe。"""
    models = root / "engines" / "vllm-ascend" / "v0.23.0" / "ascend-a3" / "models" / "Synthetic"
    models.mkdir(parents=True, exist_ok=True)
    nodes = []
    for role, role_name in (("P", "prefill"), ("D", "decode")):
        config = _engine_config(role)
        for key in (
            "data_parallel_size",
            "data_parallel_rank",
            "data_parallel_address",
            "data_parallel_rpc_port",
        ):
            config.pop(key)
        config["tensor_parallel_size"] = 1
        config["kv_transfer_config"]["kv_connector_extra_config"] = {
            "prefill": {"dp_size": 1, "tp_size": 1},
            "decode": {"dp_size": 1, "tp_size": 1},
        }
        nodes.append(
            {
                "role": role_name,
                "index": 0,
                "engine_config": config,
                "env": {},
            }
        )
    payload = {
        "schema_version": "synthetic",
        "model": {"name": "Synthetic-Ordinary", "variant_name": _ORDINARY_VARIANT},
        "scenarios": {
            "pd_disaggregation": {
                "strategies": {
                    "approved": {
                        "default_strategy": True,
                        "nodes": nodes,
                    }
                }
            }
        },
    }
    (models / "ordinary-pd.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


@pytest.fixture
def pd_root(tmp_path: Path) -> Path:
    """构造 synthetic exact PD 配置根。"""
    _write_model_root(tmp_path)
    return tmp_path


@pytest.fixture
def ordinary_pd_root(tmp_path: Path) -> Path:
    """构造普通 DP1 exact PD 配置根。"""
    _write_ordinary_model_root(tmp_path)
    return tmp_path


def _decode_input(placement: ClusterPlacement) -> PdRuntimeInput:
    """构造 decode Pod 的显式 allocation 输入(DP=4, local=2, member 2)。"""
    explicit = ExplicitPdTopology(
        pd_index=1,
        prefill=ParallelShape(dp_size=4, tp_size=8),
        decode=ParallelShape(dp_size=4, tp_size=1),
        dp_size_local=2,
    )
    return PdRuntimeInput(PdRole.DECODE, explicit, placement)


def test_ordinary_pd_pipeline_derives_tp_from_device_count(
    ordinary_pd_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证普通 PD 全链派生 TP、单进程和无 DP argv。"""
    monkeypatch.setenv("ENGINE_VERSION", "v0.23.0")
    placement = ClusterPlacement(
        master_ip="10.0.0.2",
        rank_ip="10.0.0.2",
        node_ips=["10.0.0.2"],
    )
    request = PipelineRequest(
        target=Target(_ORDINARY_VARIANT, Topology.PD_DECODE, "vllm-ascend"),
        hardware_info_path=_write_hardware(ordinary_pd_root),
        config_root=ordinary_pd_root,
        device_count=4,
        placement=placement,
        pd_input=PdRuntimeInput(PdRole.DECODE, None, placement),
    )

    resolved = resolve_pipeline(request)

    assert resolved.pd_topology is not None
    assert resolved.pd_topology.input_policy == "derived_1p1d"
    assert resolved.pd_topology.prefill == ParallelShape(1, 4)
    assert resolved.pd_topology.decode == ParallelShape(1, 4)
    assert resolved.process_plan is not None
    assert resolved.process_plan.layout == "single_process"
    assert resolved.process_plan.lifecycle == "single"
    assert len(resolved.process_plan.processes) == 1
    process = resolved.process_plan.processes[0]
    assert process.visible_devices == (0, 1, 2, 3)
    assert process.dp_rank is None
    assert process.argv[process.argv.index("--tensor-parallel-size") + 1] == "4"
    assert not any(argument.startswith("--data-parallel-") for argument in process.argv)
    assert resolved.resolution_notes["pd_tp_source"] == "device_count"


def test_pd_exact_pipeline_builds_process_plan(pd_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 strict pipeline 展开 2 个 local DP 进程，argv 为 list。"""
    monkeypatch.setenv("ENGINE_VERSION", "v0.23.0")
    request = PipelineRequest(
        target=Target(_VARIANT, Topology.PD_DECODE, "vllm-ascend"),
        hardware_info_path=_write_hardware(pd_root),
        config_root=pd_root,
        device_count=16,
        placement=ClusterPlacement(
            master_ip="10.0.0.3",
            rank_ip="10.0.0.4",
            node_ips=["10.0.0.3", "10.0.0.4"],
        ),
        pd_input=_decode_input(
            ClusterPlacement(
                master_ip="10.0.0.3",
                rank_ip="10.0.0.4",
                node_ips=["10.0.0.3", "10.0.0.4"],
            )
        ),
    )
    monkeypatch.delenv("PD_ROLE", raising=False)

    resolved = resolve_pipeline(request)

    assert resolved.pd_topology is not None
    assert resolved.pd_topology.input_policy == "explicit_allocation"
    assert resolved.process_plan is not None
    plan = resolved.process_plan
    assert plan.layout == "per_local_dp_rank"
    assert [process.dp_rank for process in plan.processes] == [2, 3]
    assert [process.visible_devices for process in plan.processes] == [(0,), (1,)]
    assert plan.endpoints == ["10.0.0.4:17000", "10.0.0.4:17001"]
    assert all(isinstance(process.argv, list) for process in plan.processes)
    assert all("--enable-auto-tool-choice" not in process.argv for process in plan.processes)
    assert all("--reasoning-parser" not in process.argv for process in plan.processes)
    assert all("--speculative-config" not in process.argv for process in plan.processes)


def test_pd_feature_overlay_applies_to_every_process_with_trace(
    pd_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 PD 复用标准 FeatureOverlay，并把 trace 投影到每个本地进程。"""
    monkeypatch.setenv("ENGINE_VERSION", "v0.23.0")
    placement = ClusterPlacement(
        master_ip="10.0.0.3",
        rank_ip="10.0.0.4",
        node_ips=["10.0.0.3", "10.0.0.4"],
    )
    request = PipelineRequest(
        target=Target(_VARIANT, Topology.PD_DECODE, "vllm-ascend"),
        hardware_info_path=_write_hardware(pd_root),
        config_root=pd_root,
        user_input=UserInput(
            feature_switches={
                "enable_auto_tool_choice": True,
                "enable_auto_think_choice": True,
            }
        ),
        device_count=16,
        placement=placement,
        pd_input=_decode_input(placement),
    )

    resolved, _, _, audit_path = run_pipeline(request, tmp_path / "feature-out")

    assert resolved.process_plan is not None
    for process in resolved.process_plan.processes:
        assert "--enable-auto-tool-choice" in process.argv
        assert process.argv[process.argv.index("--tool-call-parser") + 1] == "synthetic_tool"
        assert process.argv[process.argv.index("--tokenizer-mode") + 1] == "synthetic"
        assert process.argv[process.argv.index("--reasoning-parser") + 1] == "synthetic_reasoning"
        assert "--speculative-config" not in process.argv
        for key in ("enable_auto_tool_choice", "tool_call_parser", "tokenizer_mode", "reasoning_parser"):
            traced = process.engine_config_traces[key]
            assert traced.final_layer == "strategy_feature"
            assert any(event.layer == "strategy_feature" for event in traced.events)
    assert resolved.resolution_notes["feature_overlay.tool_calling"].startswith("applied:")
    assert resolved.resolution_notes["feature_overlay.reasoning"].startswith("applied:")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audited_process = audit["pd"]["process_plan"]["processes"][0]
    assert audited_process["engine_config"]["tool_call_parser"]["final_layer"] == "strategy_feature"
    assert "strategy_feature" in [
        event["layer"] for event in audited_process["engine_config"]["reasoning_parser"]["events"]
    ]


def test_pd_pipeline_generates_scripts_and_audit(
    pd_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证 run_pipeline 产出 fail-together 脚本、audit 与 process trace。"""
    monkeypatch.setenv("ENGINE_VERSION", "v0.23.0")
    monkeypatch.delenv("PD_ROLE", raising=False)
    placement = ClusterPlacement(
        master_ip="10.0.0.3",
        rank_ip="10.0.0.4",
        node_ips=["10.0.0.3", "10.0.0.4"],
    )
    request = PipelineRequest(
        target=Target(_VARIANT, Topology.PD_DECODE, "vllm-ascend"),
        hardware_info_path=_write_hardware(pd_root),
        config_root=pd_root,
        device_count=16,
        placement=placement,
        pd_input=_decode_input(placement),
    )
    out = tmp_path / "out"
    resolved, start, repro, audit = run_pipeline(request, out)

    assert start.exists() and repro.exists() and audit.exists()
    script = start.read_text(encoding="utf-8")
    assert "wait -n" in script  # fail-together supervisor
    assert "nic_name=$(awk" in script
    assert script.index("nic_name=$(awk") < script.index("export HCCL_IF_IP")
    assert "export HCCL_IF_IP=10.0.0.4" in script
    assert 'export GLOO_SOCKET_IFNAME="$nic_name"' in script
    assert 'export TP_SOCKET_IFNAME="$nic_name"' in script
    assert 'export HCCL_SOCKET_IFNAME="$nic_name"' in script
    assert "$local_ip" not in script
    engine_lines = [line for line in script.splitlines() if "exec vllm serve" in line]
    assert engine_lines
    assert [shlex.split(line.strip()[5:]) for line in engine_lines] == [
        process.argv for process in resolved.process_plan.processes
    ]
    assert all(f"${index}" not in line for line in engine_lines for index in range(2, 8))
    assert "echo must-not-run" not in script
    # 生成的 PD 脚本必须通过 bash -n 语法校验(与 standalone 同一护栏)
    subprocess.run(["bash", "-n", str(start)], check=True)
    subprocess.run(["bash", "-n", str(repro)], check=True)
    data = json.loads(audit.read_text(encoding="utf-8"))
    assert data["engine_config"] == {}  # PD 执行方消费 process_plan，顶层不伪造
    assert data["pd"]["role"] == "D"
    assert data["pd"]["local_allocation"]["rank_start"] == 2
    processes = data["pd"]["process_plan"]["processes"]
    assert len(processes) == 2
    assert processes[0]["dp_rank"] == 2
    assert "strategy_pd_process" in [
        event["layer"] for event in processes[0]["engine_config"]["kv_transfer_config"]["events"]
    ]
    assert resolved.pd_topology is not None


def test_pd_cli_keeps_proxy_port_out_of_engine_overrides(
    pd_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """验证 MaaS --port=18000 不再阻断 PD exact backend 规划。"""
    runtime_env = {
        "ENGINE_VERSION": "v0.23.0",
        "PD_ROLE": "D",
        "PD_INDEX": "1",
        "PD_PREFILL_DP_SIZE": "4",
        "PD_PREFILL_TP_SIZE": "8",
        "PD_DECODE_DP_SIZE": "4",
        "PD_DECODE_TP_SIZE": "1",
        "DP_SIZE_LOCAL": "2",
        "RANK_IP": "10.0.0.4",
        "MASTER_IP": "10.0.0.3",
        "NODE_IPS": "10.0.0.3,10.0.0.4",
    }
    for name, value in runtime_env.items():
        monkeypatch.setenv(name, value)
    hardware = _write_hardware(pd_root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--engine",
            "vllm-ascend",
            "--model-name",
            _VARIANT,
            "--model-path",
            "/weights/synthetic-glm51",
            "--config-root",
            str(pd_root),
            "--hardware-info",
            str(hardware),
            "--device-count",
            "16",
            "--port",
            "18000",
            "--distributed",
            "--dry-run",
        ],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "--port" in output
    assert "17000" in output and "17001" in output
    assert "/weights/synthetic-glm51" in output
    assert "vllm serve synthetic/glm51" not in output
    assert os.environ["PORT"] == "18000"


def test_pd_cli_feature_switches_reuse_model_overlay(
    pd_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """验证 MaaS 工具/思考开关在 PD dry-run 中复用模型 FeatureOverlay。"""
    runtime_env = {
        "ENGINE_VERSION": "v0.23.0",
        "PD_ROLE": "D",
        "PD_INDEX": "1",
        "PD_PREFILL_DP_SIZE": "4",
        "PD_PREFILL_TP_SIZE": "8",
        "PD_DECODE_DP_SIZE": "4",
        "PD_DECODE_TP_SIZE": "1",
        "DP_SIZE_LOCAL": "2",
        "RANK_IP": "10.0.0.4",
        "MASTER_IP": "10.0.0.3",
        "NODE_IPS": "10.0.0.3,10.0.0.4",
    }
    for name, value in runtime_env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--engine",
            "vllm-ascend",
            "--model-name",
            _VARIANT,
            "--config-root",
            str(pd_root),
            "--hardware-info",
            str(_write_hardware(pd_root)),
            "--device-count",
            "16",
            "--distributed",
            "--enable-auto-tool-choice",
            "--enable-auto-think-choice",
            "--dry-run",
        ],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "--enable-auto-tool-choice" in output
    assert "--tool-call-parser synthetic_tool" in output
    assert "--tokenizer-mode synthetic" in output
    assert "--reasoning-parser synthetic_reasoning" in output
    assert "--speculative-config" not in output
