from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from wings_ctl.core.models import ClusterPlacement, PipelineRequest, Target, UserInput
from wings_ctl.core.topology import Topology
from wings_ctl.engines.mindie.config_v230 import (
    build_config_overrides,
    build_full_config,
)
from wings_ctl.engines.mindie.dual_node import MindieDualNodePlan
from wings_ctl.engines.mindie.runtime import (
    build_launch_plan,
    prepare_control_ranktable,
)
from wings_ctl.pipeline import resolve_pipeline, run_pipeline
from wings_ctl.translators.cli_translator import CLITranslator


def _write_ranktable(path: Path) -> None:
    """写入两个节点、每节点两张本地逻辑卡的最小有效拓扑。"""
    path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "server_count": "2",
                "server_list": [
                    {
                        "server_id": "10.0.0.1",
                        "device": [
                            {"device_id": "0", "device_ip": "192.168.0.1", "rank_id": "0"},
                            {"device_id": "1", "device_ip": "192.168.0.2", "rank_id": "1"},
                        ],
                    },
                    {
                        "server_id": "10.0.0.2",
                        "device": [
                            {"device_id": "0", "device_ip": "192.168.1.1", "rank_id": "2"},
                            {"device_id": "1", "device_ip": "192.168.1.2", "rank_id": "3"},
                        ],
                    },
                ],
                "status": "completed",
            }
        ),
        encoding="utf-8",
    )


def _assert_normalized_ranktable(target: Path) -> None:
    """校验 prepare 写出的 ranktable 已归一化为容器本地 device_id。"""
    installed = json.loads(target.read_text(encoding="utf-8"))
    assert installed["server_count"] == "2"
    assert len(installed["server_list"]) == 2
    assert [d["device_id"] for d in installed["server_list"][0]["device"]] == ["0", "1"]
    assert [d["device_id"] for d in installed["server_list"][1]["device"]] == ["0", "1"]


def _request(repo_root: Path, rank_ip: str, *, model_name: str = "demo") -> PipelineRequest:
    translated, dropped = CLITranslator.translate_overrides(
        {
            "model_path": "/models/demo",
            "model_name": model_name,
            "input_length": 2048,
            "output_length": 2048,
            "max_model_len": 4096,
        },
        "mindie",
    )
    return PipelineRequest(
        target=Target(
            model_name=model_name,
            topology=Topology.MULTI_NODE,
            engine="mindie",
        ),
        hardware_info_path=repo_root / "tests" / "fixtures" / "hardware_info_ascend910b.json",
        config_root=repo_root / "config",
        user_input=UserInput(cli_overrides=translated, cli_dropped=dropped),
        device_count=2,
        placement=ClusterPlacement(
            rank_ip=rank_ip,
            node_ips=["10.0.0.1", "10.0.0.2"],
            master_ip="10.0.0.1",
        ),
    )


def _dual_node_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rank_ip: str = "10.0.0.1") -> MindieDualNodePlan:
    """构造 ranktable 指向本机临时路径的双机领域计划（resolve 阶段不读内容）。"""
    from wings_ctl.engines.mindie import ranktable

    source = tmp_path / "rank_table_all.json"
    target = tmp_path / "shared" / "hccl_ranktable.json"
    monkeypatch.setattr(ranktable, "RANKTABLE_SOURCE_PATH", source)
    monkeypatch.setattr(ranktable, "RANKTABLE_TARGET_PATH", target)
    repo_root = Path(__file__).resolve().parents[2]
    resolved = resolve_pipeline(_request(repo_root, rank_ip))
    plan = resolved.engine_state
    assert isinstance(plan, MindieDualNodePlan)
    return plan


def test_ranktable_default_paths_keep_container_posix_form() -> None:
    """固定容器路径不能随脚本生成主机切换为 Windows 分隔符。"""
    from wings_ctl.engines.mindie.ranktable import resolve_ranktable_paths

    plan = resolve_ranktable_paths()

    assert str(plan.source_path) == "/workspace/rank_table_all.json"
    assert str(plan.target_path) == "/shared-volume/hccl_ranktable.json"


@pytest.mark.parametrize(
    ("rank_ip", "node_rank"),
    [
        ("10.0.0.1", 0),
        ("10.0.0.2", 1),
    ],
)
def test_dual_node_plan_projects_local_and_global_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rank_ip: str,
    node_rank: int,
) -> None:
    """两节点共享全局 tp，但各自使用本地 worldSize、node rank 与节点 IP。"""
    plan = _dual_node_plan(tmp_path, monkeypatch, rank_ip)

    assert (plan.node_rank, plan.local_world_size, plan.global_world_size) == (node_rank, 2, 4)
    assert (plan.tp, plan.dp, plan.local_ip) == (4, 1, rank_ip)
    assert plan.local_device_ids == (0, 1)

    overrides = build_config_overrides(plan)
    assert overrides["backend"] == {
        "npuDeviceIds": [[0, 1]],
        "multiNodesInferEnabled": True,
    }
    assert overrides["model_config"]["worldSize"] == 2
    assert overrides["model_config"]["tp"] == 4
    assert overrides["model_config"]["dp"] == 1

    script = "\n".join(build_launch_plan(plan).pre_start_lines)
    # ranktable 由 control 侧 prepare_control_ranktable 安装，脚本只校验共享目标。
    assert "# MindIE dual-node ranktable prepared by wings-control" in script
    assert "export RANK_TABLE_FILE=" in script
    assert f'export HCCL_IF_IP="${{HCCL_IF_IP:-{rank_ip}}}"' in script
    assert f"export MIES_CONTAINER_IP={rank_ip}" in script
    assert "unset MASTER_ADDR MASTER_PORT RANK LOCAL_RANK WORLD_SIZE NPU_DEVICE_IDS" in script
    assert "export RANK=" not in script
    assert "export WORLD_SIZE=" not in script
    assert "export MASTER_ADDR=" not in script


def test_prepare_installs_normalized_ranktable_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """控制侧把物理卡号归一化为容器本地序号并原子安装，不改动部署侧源。"""
    plan = _dual_node_plan(tmp_path, monkeypatch)
    source = plan.ranktable.source_path
    target = plan.ranktable.target_path
    _write_ranktable(source)
    source_bytes = source.read_bytes()

    prepare_control_ranktable(plan)

    assert source.read_bytes() == source_bytes  # 不改部署侧源
    _assert_normalized_ranktable(target)
    if os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o640
    assert not list(target.parent.glob("*.tmp"))


def test_prepare_waits_for_delayed_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """部署文件短暂晚到时等待一次后继续，且不破坏原子安装边界。"""
    plan = _dual_node_plan(tmp_path, monkeypatch)
    source = plan.ranktable.source_path
    target = plan.ranktable.target_path

    monkeypatch.setenv("WINGS_MINDIE_RANKTABLE_WAIT_SECONDS", "7")
    monkeypatch.setattr(time, "sleep", lambda _seconds: _write_ranktable(source))

    with caplog.at_level("INFO"):
        prepare_control_ranktable(plan)

    assert "waiting up to 7s for ranktable" in caplog.text
    _assert_normalized_ranktable(target)


def test_prepare_times_out_when_source_stays_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """源文件始终缺失时仍有界失败，避免 engine 容器无限挂起。"""
    plan = _dual_node_plan(tmp_path, monkeypatch)
    target = plan.ranktable.target_path
    monkeypatch.setenv("WINGS_MINDIE_RANKTABLE_WAIT_SECONDS", "0")

    with pytest.raises(ValueError, match="timed out after 0s waiting for ranktable"):
        prepare_control_ranktable(plan)
    assert not target.exists()


@pytest.mark.parametrize("timeout_value", ["invalid", "-1"])
def test_prepare_rejects_invalid_wait_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    timeout_value: str,
) -> None:
    """非法或负超时必须立即失败，不能悄悄改成无限等待。"""
    plan = _dual_node_plan(tmp_path, monkeypatch)
    target = plan.ranktable.target_path

    monkeypatch.setenv("WINGS_MINDIE_RANKTABLE_WAIT_SECONDS", timeout_value)

    with pytest.raises(ValueError, match="invalid WINGS_MINDIE_RANKTABLE_WAIT_SECONDS"):
        prepare_control_ranktable(plan)
    assert not target.exists()


def test_prepare_does_not_retry_non_missing_read_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """权限等非 ENOENT 错误保持 fail-fast，等待兜底不能掩盖挂载权限问题。"""
    plan = _dual_node_plan(tmp_path, monkeypatch)
    target = plan.ranktable.target_path
    sleep_calls: list[float] = []
    monkeypatch.setattr(time, "sleep", sleep_calls.append)

    def _permission_denied(*_args: object, **_kwargs: object) -> object:
        raise PermissionError("permission denied by test")

    monkeypatch.setattr("wings_ctl.engines.mindie.runtime.open", _permission_denied)

    with pytest.raises(ValueError, match="cannot read ranktable"):
        prepare_control_ranktable(plan)
    assert sleep_calls == []
    assert not target.exists()


def test_prepare_reprocesses_latest_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """部署侧文件是最终事实，每次 prepare 都按当前源内容重新归一化。"""
    plan = _dual_node_plan(tmp_path, monkeypatch)
    source = plan.ranktable.source_path
    target = plan.ranktable.target_path
    _write_ranktable(source)

    prepare_control_ranktable(plan)
    document = json.loads(source.read_text(encoding="utf-8"))
    document["note"] = "latest"
    source.write_text(json.dumps(document), encoding="utf-8")
    prepare_control_ranktable(plan)

    installed = json.loads(target.read_text(encoding="utf-8"))
    assert installed["note"] == "latest"
    _assert_normalized_ranktable(target)


def test_ranktable_content_is_not_read_during_prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """resolve 阶段只保存固定路径，即使内容不是 JSON 也不在 resolve 侧解析。"""
    from wings_ctl.engines.mindie import ranktable

    source = tmp_path / "rank_table_all.json"
    source.write_text("deployment-owned opaque payload", encoding="utf-8")
    monkeypatch.setattr(ranktable, "RANKTABLE_SOURCE_PATH", source)
    repo_root = Path(__file__).resolve().parents[2]

    resolved = resolve_pipeline(_request(repo_root, "10.0.0.1"))
    plan = resolved.engine_state
    assert isinstance(plan, MindieDualNodePlan)
    assert plan.ranktable.source_path == source
    assert plan.local_device_ids == (0, 1)


def test_dual_node_uses_deployment_device_count_without_parsing_ranktable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """并行规模来自部署上下文；固定 ranktable 内容由 MindIE/HCCL 自行消费。"""
    from wings_ctl.engines.mindie import ranktable

    source = tmp_path / "rank_table_all.json"
    _write_ranktable(source)
    monkeypatch.setattr(ranktable, "RANKTABLE_SOURCE_PATH", source)
    repo_root = Path(__file__).resolve().parents[2]
    request = _request(repo_root, "10.0.0.1")
    request = PipelineRequest(
        target=request.target,
        hardware_info_path=request.hardware_info_path,
        config_root=request.config_root,
        user_input=request.user_input,
        device_count=1,
        placement=request.placement,
    )

    resolved = resolve_pipeline(request)
    plan = resolved.engine_state
    assert isinstance(plan, MindieDualNodePlan)
    assert plan.local_world_size == 1
    assert plan.global_world_size == 2
    assert (plan.tp, plan.dp) == (2, 1)


def test_deepseek_dual_node_enables_ep_from_model_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """用户不传 EP；命中 DeepSeek profile 后按全局规模生成 MoE 并行字段。"""
    from wings_ctl.engines.mindie import ranktable

    source = tmp_path / "rank_table_all.json"
    target = tmp_path / "shared" / "hccl_ranktable.json"
    source.write_text("opaque-ranktable", encoding="utf-8")
    monkeypatch.setattr(ranktable, "RANKTABLE_SOURCE_PATH", source)
    monkeypatch.setattr(ranktable, "RANKTABLE_TARGET_PATH", target)
    repo_root = Path(__file__).resolve().parents[2]

    resolved = resolve_pipeline(_request(repo_root, "10.0.0.1", model_name="DeepSeek-R1-W8A8"))
    plan = resolved.engine_state
    assert isinstance(plan, MindieDualNodePlan)
    assert plan.common.model_policy.ep_enabled is True
    assert plan.parallel.moe_tp == 1
    assert plan.parallel.moe_ep == 4
    assert plan.parallel.ep_level == 1

    overrides = build_config_overrides(plan)
    assert overrides["root"] == {"enable_ep_moe": True}
    model_config = overrides["model_config"]
    assert model_config["tp"] == 4
    assert model_config["dp"] == 1
    assert model_config["moe_tp"] == 1
    assert model_config["moe_ep"] == 4
    assert model_config["models"] == {"deepseekv2": {"ep_level": 1}}
    assert resolved.resolution_notes["mindie_ep_decision_source"] == "model_yaml"

    full_config = build_full_config(plan)
    assert full_config["enable_ep_moe"] is True
    assert full_config["ServerConfig"]["managementPort"] == 1026
    assert full_config["BackendConfig"]["ModelDeployConfig"]["ModelConfig"][0]["moe_ep"] == 4

    script = "\n".join(build_launch_plan(plan).pre_start_lines)
    assert script.index("source /usr/local/Ascend/mindie/set_env.sh") < script.index(
        "# ─── MindIE static environment from resolved YAML ───"
    )
    assert "export RANK_TABLE_FILE=" in script


def test_deepseek_distill_does_not_enable_ep() -> None:
    """名称含 R1 的 Distill 稠密模型不得误命中 DeepSeek MoE profile。"""
    repo_root = Path(__file__).resolve().parents[2]
    resolved = resolve_pipeline(
        _request(
            repo_root,
            "10.0.0.1",
            model_name="DeepSeek-R1-Distill-Qwen-32B",
        )
    )
    plan = resolved.engine_state
    assert isinstance(plan, MindieDualNodePlan)
    assert plan.common.model_policy.ep_enabled is False
    assert plan.parallel.moe_ep is None
    assert "root" not in build_config_overrides(plan)


def test_dual_node_pipeline_generates_executable_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """完整流水线由公共层统一监督 daemon，并产出可追踪审计。"""
    from wings_ctl.engines.mindie import ranktable

    source = tmp_path / "rank_table_all.json"
    target = tmp_path / "shared" / "hccl_ranktable.json"
    _write_ranktable(source)
    monkeypatch.setattr(ranktable, "RANKTABLE_SOURCE_PATH", source)
    monkeypatch.setattr(ranktable, "RANKTABLE_TARGET_PATH", target)
    monkeypatch.setenv("WINGS_START_LOG", str(tmp_path / "wings_start.log"))
    repo_root = Path(__file__).resolve().parents[2]

    resolved, start_path, repro_path, audit_path = run_pipeline(_request(repo_root, "10.0.0.2"), tmp_path / "out")

    assert isinstance(resolved.engine_state, MindieDualNodePlan)
    start_script = start_path.read_text(encoding="utf-8")
    # ranktable 由 control 侧在 start_command.sh 可见前安装；脚本只校验共享目标。
    assert "# MindIE dual-node ranktable prepared by wings-control" in start_script
    assert (
        start_script.index("source /usr/local/Ascend/mindie/set_env.sh")
        < start_script.index("export RANK_TABLE_FILE=")
        < start_script.index("python3 << 'WINGS_MINDIE_CONFIG_EOF'")
    )
    assert start_script.count("./bin/mindieservice_daemon &") == 1
    assert 'wait "$ENGINE_PID"' in start_script
    assert start_script.rstrip().endswith('exit "$ENGINE_EXIT_CODE"')
    # rank1 只启动引擎；公共 multi_node_index 契约确保分析器不会重复运行。
    assert "log_analyzer config" not in start_script
    assert repro_path.is_file()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["version"]["engine"] == "mindie"
    assert audit["topology"] == "multi_node"
    assert audit["param_validation"]["policy"] == "fail_fast"
    assert audit["resolution_notes"]["mindie_node_rank"] == "1"
    assert audit["resolution_notes"]["mindie_local_world_size"] == "2"
    assert audit["resolution_notes"]["mindie_global_world_size"] == "4"
    assert audit["resolution_notes"]["mindie_tp"] == "4"
    assert audit["resolution_notes"]["mindie_dp"] == "1"
