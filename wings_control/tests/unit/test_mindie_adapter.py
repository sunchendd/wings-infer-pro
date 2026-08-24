from __future__ import annotations

import json
from pathlib import Path

import pytest

from wings_ctl.core.models import (
    ClusterPlacement,
    EngineVersion,
    HardwareContext,
    PipelineRequest,
    ResolvedConfig,
    SourceEvent,
    Target,
    TracedValue,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.mindie_adapter import (
    build_config_overrides,
    build_launch_parts,
    validate_resolved_config,
)
from wings_ctl.engines.mindie.standalone import resolve_standalone_plan
from wings_ctl.engines.registry import format_launch_summary
from wings_ctl.rendering.script_builder import build_scripts


def _traced(key: str, value: object, *, layer: str = "test") -> TracedValue:
    event = SourceEvent(
        action="set",
        layer=layer,
        value=value,
        source_file="test.yaml",
        source_path=f"engine_config.{key}",
    )
    return TracedValue(
        final_value=value,
        final_layer=layer,
        source_file="test.yaml",
        source_path=f"engine_config.{key}",
        events=[event],
    )


def _resolved(
    *,
    topology: Topology = Topology.STANDALONE,
    device: str = "ascend",
    version: str = "2.3.0",
    is_fallback: bool = False,
    extra: dict[str, object] | None = None,
) -> ResolvedConfig:
    values: dict[str, object] = {
        "host": "0.0.0.0",
        "port": 17000,
        "model": "/models/Qwen-Demo",
        "served_model_name": "Qwen-Demo",
        "max_seq_len": 6144,
        "max_input_token_len": 4096,
        "max_iter_times": 2048,
        "max_prefill_tokens": 8192,
        "trust_remote_code": True,
        "npu_memory_fraction": 0.95,
        "local_device_count": 8,
    }
    values.update(extra or {})
    return ResolvedConfig(
        topology=topology,
        hardware=HardwareContext(
            hardware_family="Ascend910B_64G",
            device=device,
        ),
        engine="mindie",
        engine_version=EngineVersion(
            requested=version,
            resolved=version,
            is_fallback=is_fallback,
            has_version_dir=True,
        ),
        engine_config_traces={key: _traced(key, value) for key, value in values.items()},
        env_traces={},
        source_files=["test.yaml"],
    )


def test_build_config_overrides_projects_minimal_schema() -> None:
    overrides = build_config_overrides(_resolved())

    assert overrides["server"] == {"ipAddress": "0.0.0.0", "port": 17000}
    assert overrides["backend"] == {
        "npuDeviceIds": [list(range(8))],
        "multiNodesInferEnabled": False,
    }
    assert overrides["model_config"]["worldSize"] == 8
    assert overrides["model_config"]["modelWeightPath"] == "/models/Qwen-Demo"
    assert overrides["model_deploy"] == {
        "maxSeqLen": 6144,
        "maxInputTokenLen": 4096,
    }
    assert overrides["schedule"]["maxIterTimes"] == 2048


def test_standalone_default_host_uses_runtime_rank_ip() -> None:
    """MindIE 禁止监听 0.0.0.0 时，把通用默认值替换为当前 Pod IP。"""
    resolved = _resolved()
    resolved.engine_config_traces["host"] = _traced("host", "0.0.0.0", layer="builtin_default")
    request = PipelineRequest(
        target=Target(model_name="Qwen-Demo", topology=Topology.STANDALONE, engine="mindie"),
        hardware_info_path=Path("hardware_info.json"),
        placement=ClusterPlacement(rank_ip="10.254.84.65"),
    )

    plan = resolve_standalone_plan(resolved, request)

    assert plan.common.host == "10.254.84.65"


def test_standalone_explicit_host_wins_over_runtime_rank_ip() -> None:
    """用户或模型显式 host 不能被部署 placement 静默覆盖。"""
    resolved = _resolved(extra={"host": "127.0.0.1"})
    request = PipelineRequest(
        target=Target(model_name="Qwen-Demo", topology=Topology.STANDALONE, engine="mindie"),
        hardware_info_path=Path("hardware_info.json"),
        placement=ClusterPlacement(rank_ip="10.254.84.65"),
    )

    plan = resolve_standalone_plan(resolved, request)

    assert plan.common.host == "127.0.0.1"


def test_launch_script_uses_common_supervised_pid_lifecycle(tmp_path: Path) -> None:
    resolved = _resolved()
    argv, pre_start, preview = build_launch_parts(resolved)

    assert argv == ["./bin/mindieservice_daemon"]
    assert any("MIES_CONFIG_JSON_PATH" in line for line in pre_start)
    assert not any("${MINDIE_WORK_DIR}/conf/config.json" in line for line in pre_start)
    assert "config overrides" in preview
    assert format_launch_summary(resolved).startswith("launch:\n# MindIE external config:")

    start_path, repro_path = build_scripts(resolved, tmp_path)
    start = start_path.read_text(encoding="utf-8")
    repro = repro_path.read_text(encoding="utf-8")

    assert "external config installed" in start
    assert "MIES_CONFIG_JSON_PATH=/shared-volume/mindie/config.json" in start
    assert start.count("./bin/mindieservice_daemon &") == 1
    assert 'wait "$ENGINE_PID"' in start
    assert start.rstrip().endswith('exit "$ENGINE_EXIT_CODE"')
    assert "# local_device_count=8 <- test" in repro
    assert repro.count("./bin/mindieservice_daemon &") == 1
    assert repro.rstrip().endswith('exit "$ENGINE_EXIT_CODE"')


def test_embedded_python_writes_project_owned_full_config_atomically(tmp_path: Path, monkeypatch) -> None:
    resolved = _resolved()
    _argv, pre_start, _preview = build_launch_parts(resolved)
    start = pre_start.index("python3 << 'WINGS_MINDIE_CONFIG_EOF'") + 1
    end = pre_start.index("WINGS_MINDIE_CONFIG_EOF")
    python_body = "\n".join(pre_start[start:end])
    payload_line = next(line for line in pre_start if line.startswith("export _WINGS_MINDIE_CONFIG_B64="))
    payload = payload_line.split("=", 1)[1]

    config_path = tmp_path / "shared" / "mindie" / "config.json"
    monkeypatch.setenv("_WINGS_MINDIE_CONFIG_TARGET", str(config_path))
    monkeypatch.setenv("_WINGS_MINDIE_CONFIG_B64", payload)

    exec(compile(python_body, "<mindie-config-merge>", "exec"), {})

    merged = json.loads(config_path.read_text(encoding="utf-8"))
    assert merged["Version"] == "1.0.0"
    assert "_comment" not in merged
    assert merged["ServerConfig"]["managementPort"] == 1026
    assert merged["ServerConfig"]["port"] == 17000
    backend = merged["BackendConfig"]
    assert backend["npuDeviceIds"] == [list(range(8))]
    assert backend["multiNodesInferEnabled"] is False
    assert backend["ModelDeployConfig"]["ModelConfig"][0]["worldSize"] == 8
    assert not list(config_path.parent.glob("*.tmp"))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"device": "nvidia"}, "requires Ascend"),
        ({"version": "2.4.0"}, "exact 2.3.0"),
        ({"is_fallback": True}, "exact 2.3.0"),
    ],
)
def test_minimal_scope_is_fail_fast(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises((ValueError, NotImplementedError), match=message):
        validate_resolved_config(_resolved(**kwargs))


def test_distributed_direct_call_requires_pipeline_prepare() -> None:
    """双机必须带 placement/ranktable 生成领域计划，不能由兼容 facade 猜测。"""
    with pytest.raises(ValueError, match="distributed state is missing"):
        validate_resolved_config(_resolved(topology=Topology.MULTI_NODE))


def test_unknown_engine_parameter_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported engine_config key.*tp"):
        validate_resolved_config(_resolved(extra={"tp": 8}))


def test_sequence_length_contract_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_seq_len must be >="):
        validate_resolved_config(_resolved(extra={"max_seq_len": 4096}))


def test_ep_parallelism_product_is_fail_fast() -> None:
    """模型 YAML 的 moe_tp 与实际卡数不整除时不能猜测降级。"""
    with pytest.raises(ValueError, match="parallel_world_size divisible"):
        validate_resolved_config(
            _resolved(
                extra={
                    "mindie_is_moe": True,
                    "mindie_ep_enabled": True,
                    "mindie_ep_policy": "full_world",
                    "mindie_moe_tp": 3,
                    "mindie_ep_level": 1,
                    "mindie_model_family": "deepseekv2",
                }
            )
        )
