"""PD per-process trace、rank、设备、endpoint 与 argv 计划测试。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from wings_ctl.core.config_resolver import _build_pd_process_plan
from wings_ctl.core.models import (
    ClusterPlacement,
    ConnectorProfile,
    EngineVersion,
    HardwareContext,
    KvPortPolicy,
    ParallelShape,
    PdRole,
    PdRuntimeSpec,
    ResolvedConfig,
    ResolvedPdTopology,
    SourceEvent,
    TracedValue,
)
from wings_ctl.core.topology import Topology


def _trace(value: object, key: str) -> TracedValue:
    """构造带 model_scenario 来源的静态 trace。"""
    event = SourceEvent("set", "model_scenario", value, "model.yaml", f"engine_config.{key}")
    return TracedValue(value, "model_scenario", "model.yaml", f"engine_config.{key}", [event])


def _runtime(
    *,
    engine_id_policy: str = "omit",
    kv_base: int = 36000,
    kv_stride: int = 0,
    rpc_port: int = 12890,
    listener_span: str = "single",
) -> object:
    """构造合法 per-local-rank runtime spec。"""
    return PdRuntimeSpec(
        topology_input_policy="explicit_allocation",
        prefill_shape=ParallelShape(2, 4),
        decode_shape=ParallelShape(4, 1),
        instance_member_count=2,
        process_layout="per_local_dp_rank",
        dp_launch_policy="external_rank",
        endpoint_policy="per_process",
        backend_port_base=17000,
        data_parallel_rpc_port=rpc_port,
        connector_profile=ConnectorProfile(
            connector_name="MooncakeConnectorV1",
            engine_id_policy=engine_id_policy,
            kv_port_policy=KvPortPolicy(
                mode="from_pd_index",
                base=kv_base,
                instance_stride=100,
                process_stride=kv_stride,
                listener_span=listener_span,
            ),
            listener_owner_scope="per_pod_connector_group",
        ),
    )


def _resolved(*, head: bool = False) -> ResolvedConfig:
    """构造 decode Pod 的静态解析结果与规范 topology。"""
    config = {
        "model": _trace("synthetic/model", "model"),
        "tensor_parallel_size": _trace(1, "tensor_parallel_size"),
        "kv_transfer_config": _trace(
            {"kv_connector": "MooncakeConnectorV1", "kv_role": "kv_consumer"},
            "kv_transfer_config",
        ),
    }
    topology = ResolvedPdTopology(
        input_policy="explicit_allocation",
        role=PdRole.DECODE,
        instance_index=3,
        prefill=ParallelShape(2, 4),
        decode=ParallelShape(4, 1),
        dp_size_local=2,
        placement=ClusterPlacement(
            master_ip="10.0.0.1",
            rank_ip="10.0.0.1" if head else "10.0.0.2",
            node_ips=["10.0.0.1", "10.0.0.2"],
        ),
        member_index=0 if head else 1,
        rank_start=0 if head else 2,
        rank_end_exclusive=2 if head else 4,
    )
    return ResolvedConfig(
        topology=Topology.PD_DECODE,
        hardware=HardwareContext("ascend910", "ascend"),
        engine="vllm-ascend",
        engine_version=EngineVersion("v0.23.0", "0.23.0", False, True),
        engine_config_traces=config,
        env_traces={},
        source_files=["model.yaml"],
        pd_topology=topology,
    )


def _ordinary_runtime() -> PdRuntimeSpec:
    """构造普通 1P1D 的单进程 runtime spec。"""
    return PdRuntimeSpec(
        topology_input_policy="derived_1p1d",
        prefill_shape=ParallelShape(1, 1),
        decode_shape=ParallelShape(1, 1),
        instance_member_count=1,
        process_layout="single_process",
        dp_launch_policy="none",
        endpoint_policy="per_process",
        backend_port_base=17000,
        data_parallel_rpc_port=None,
        connector_profile=ConnectorProfile(
            connector_name="SyntheticConnector",
            engine_id_policy="from_pd_index",
            kv_port_policy=KvPortPolicy(
                mode="from_pd_index",
                base=30000,
                instance_stride=100,
                listener_span="single",
            ),
            listener_owner_scope="per_pod_connector_group",
        ),
    )


def _ordinary_resolved(device: str, engine: str, device_count: int) -> ResolvedConfig:
    """构造已按 device-count 派生 P/D TP 的普通 Decode Pod。"""
    config = {
        "model": _trace("synthetic/model", "model"),
        "tensor_parallel_size": _trace(1, "tensor_parallel_size"),
        "kv_transfer_config": _trace(
            {"kv_connector": "SyntheticConnector", "kv_role": "kv_consumer"},
            "kv_transfer_config",
        ),
    }
    topology = ResolvedPdTopology(
        input_policy="derived_1p1d",
        role=PdRole.DECODE,
        instance_index=1,
        prefill=ParallelShape(1, device_count),
        decode=ParallelShape(1, device_count),
        dp_size_local=1,
        placement=ClusterPlacement(
            master_ip="10.0.0.2",
            rank_ip="10.0.0.2",
            node_ips=["10.0.0.2"],
        ),
        member_index=0,
        rank_start=0,
        rank_end_exclusive=1,
    )
    return ResolvedConfig(
        topology=Topology.PD_DECODE,
        hardware=HardwareContext(f"synthetic-{device}", device),
        engine=engine,
        engine_version=EngineVersion("v1", "1", False, True),
        engine_config_traces=config,
        env_traces={},
        source_files=["model.yaml"],
        pd_topology=topology,
    )


@pytest.mark.parametrize(
    ("device", "engine", "visible_env"),
    [
        ("ascend", "vllm-ascend", "ASCEND_RT_VISIBLE_DEVICES"),
        ("nvidia", "vllm", "CUDA_VISIBLE_DEVICES"),
    ],
)
def test_ordinary_process_uses_all_devices_without_dp_flags(
    device: str,
    engine: str,
    visible_env: str,
) -> None:
    """验证 Ascend/NVIDIA 普通 PD 均以 TP=device-count 启动唯一进程。"""
    plan = _build_pd_process_plan(_ordinary_resolved(device, engine, 4), _ordinary_runtime(), device_count=4)

    assert plan.layout == "single_process"
    assert plan.lifecycle == "single"
    assert plan.endpoints == ["10.0.0.2:17000"]
    assert len(plan.processes) == 1
    process = plan.processes[0]
    assert process.dp_rank is None
    assert process.visible_devices == (0, 1, 2, 3)
    assert process.env_traces[visible_env].final_value == "0,1,2,3"
    tp_position = process.argv.index("--tensor-parallel-size")
    assert process.argv[tp_position + 1] == "4"
    assert not any(argument.startswith("--data-parallel-") for argument in process.argv)
    assert process.engine_config_traces["kv_transfer_config"].final_value["kv_connector_extra_config"] == {
        "prefill": {"dp_size": 1, "tp_size": 4},
        "decode": {"dp_size": 1, "tp_size": 4},
    }
    assert [event.layer for event in process.engine_config_traces["tensor_parallel_size"].events] == [
        "model_scenario",
        "strategy_pd_process",
    ]
    assert not [listener for listener in plan.listeners if listener.name == "dp_rpc"]


def test_process_plan_expands_rank_devices_endpoints_and_argv() -> None:
    """验证 local ranks 有序展开，PD_INDEX 不参与 rank，argv 保持 list。"""
    plan = _build_pd_process_plan(_resolved(), _runtime(), device_count=2)

    assert plan.layout == "per_local_dp_rank"
    assert plan.lifecycle == "fail_together"
    assert [process.dp_rank for process in plan.processes] == [2, 3]
    assert [process.visible_devices for process in plan.processes] == [(0,), (1,)]
    assert plan.endpoints == ["10.0.0.2:17000", "10.0.0.2:17001"]
    assert all(isinstance(process.argv, list) for process in plan.processes)
    assert "--data-parallel-rank" in plan.processes[0].argv


def test_process_plan_preserves_static_trace_before_dynamic_event() -> None:
    """验证 process 动态覆盖追加 trace event，不抹掉 recipe 来源。"""
    process = _build_pd_process_plan(_resolved(), _runtime(), device_count=2).processes[0]

    kv_trace = process.engine_config_traces["kv_transfer_config"]
    assert [event.layer for event in kv_trace.events] == [
        "model_scenario",
        "strategy_pd_process",
    ]
    assert kv_trace.final_value["kv_connector"] == "MooncakeConnectorV1"
    assert kv_trace.final_value["kv_port"] == 36300
    assert kv_trace.final_value["kv_connector_extra_config"] == {
        "prefill": {"dp_size": 2, "tp_size": 4},
        "decode": {"dp_size": 4, "tp_size": 1},
    }


def test_process_plan_from_pd_index_adds_profile_scoped_engine_id() -> None:
    """验证仅 from_pd_index exact profile 注入字符串 engine_id。"""
    process = _build_pd_process_plan(_resolved(), _runtime(engine_id_policy="from_pd_index"), device_count=2).processes[
        0
    ]

    assert process.engine_config_traces["kv_transfer_config"].final_value["engine_id"] == "3"


def test_process_plan_runtime_uuid_omits_engine_id() -> None:
    """验证 runtime UUID profile 不生成 engine_id。"""
    process = _build_pd_process_plan(_resolved(), _runtime(), device_count=2).processes[0]

    assert "engine_id" not in process.engine_config_traces["kv_transfer_config"].final_value


def test_process_plan_listener_span_reserves_base_through_device_count() -> None:
    """验证官方定义的闭区间包含 base 和 base+device_count。"""
    plan = _build_pd_process_plan(_resolved(), _runtime(listener_span="device_count_plus_one"), device_count=16)
    kv_listeners = [listener for listener in plan.listeners if listener.name == "kv"]

    assert kv_listeners, "应生成 kv listener"
    # kv_port = 36000 + instance_index(3)*100 = 36300；官方范围为 base..base+num_chips。
    assert all((listener.port_start, listener.port_end) == (36300, 36316) for listener in kv_listeners)
    assert all(listener.port_end - listener.port_start + 1 == 17 for listener in kv_listeners)


def test_process_plan_registers_dp_rpc_listener_only_on_rank_zero_pod() -> None:
    """DP RPC address 指向 Instance master，worker Pod 不应伪报本地 listener。"""
    worker_plan = _build_pd_process_plan(_resolved(), _runtime(), device_count=2)
    head_plan = _build_pd_process_plan(_resolved(head=True), _runtime(), device_count=2)

    assert not [listener for listener in worker_plan.listeners if listener.name == "dp_rpc"]
    assert len([listener for listener in head_plan.listeners if listener.name == "dp_rpc"]) == 1


def test_process_plan_rejects_ambient_engine_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证多 endpoint PD 不接受 ambient ENGINE_PORT 静默覆盖。"""
    monkeypatch.setenv("ENGINE_PORT", "17000")

    with pytest.raises(ValueError, match="ENGINE_PORT"):
        _build_pd_process_plan(_resolved(), _runtime(), device_count=2)


def test_process_plan_rejects_listener_conflict() -> None:
    """验证 RPC 与 API listener 冲突在脚本生成前失败。"""
    with pytest.raises(ValueError, match="PD listener conflict"):
        _build_pd_process_plan(_resolved(head=True), _runtime(rpc_port=17000), device_count=2)


def test_process_plan_rejects_unknown_endpoint_policy() -> None:
    """验证未知 endpoint 策略不能静默关闭 endpoint 注册。"""
    runtime = replace(_runtime(), endpoint_policy="typo")

    with pytest.raises(ValueError, match="endpoint_policy.*typo"):
        _build_pd_process_plan(_resolved(), runtime, device_count=2)


def test_process_plan_rejects_unknown_kv_port_mode() -> None:
    """验证未知 KV port mode 不能静默跳过 KV listener 和参数。"""
    runtime = _runtime()
    invalid_kv_policy = replace(runtime.connector_profile.kv_port_policy, mode="typo")
    invalid_connector = replace(runtime.connector_profile, kv_port_policy=invalid_kv_policy)
    runtime = replace(runtime, connector_profile=invalid_connector)

    with pytest.raises(ValueError, match="kv_port_policy.mode.*typo"):
        _build_pd_process_plan(_resolved(), runtime, device_count=2)


def test_process_plan_rejects_unknown_listener_owner_scope() -> None:
    """验证未知 listener owner scope 不能退化成共享 connector listener。"""
    runtime = _runtime()
    invalid_connector = replace(runtime.connector_profile, listener_owner_scope="typo")
    runtime = replace(runtime, connector_profile=invalid_connector)

    with pytest.raises(ValueError, match="listener_owner_scope.*typo"):
        _build_pd_process_plan(_resolved(), runtime, device_count=2)
