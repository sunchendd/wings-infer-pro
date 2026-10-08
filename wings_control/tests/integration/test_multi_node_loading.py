"""Step 3.1-b — multi_node 模板加载(无运行时上下文 → 占位不注入)集成测试。

无 RANK_IP/NODE_IPS 时:逐节点深合并、占位符字面保留、顶层留空、产占位脚本(无 exec)。
固定输入→固定输出:GLM-4.5(vllm-ascend / ascend-a3,head+worker 两节点)。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wings_ctl.core.config_resolver import _resolve_multi_node, normalize_nodes, resolve_config
from wings_ctl.core.models import PipelineRequest, ResolvedEnv, Target, UserInput
from wings_ctl.core.topology import Topology
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.pipeline import run_pipeline

# 改指 ascend-a2 GLM-4.5:config 8b2f5b5 误删 a3 该模型 multi_node 场景(config bug,docs/14);
# a2 multi_node 块等价,断言不变。a3 修好后可回指。
_HW = {"hardware_family": "ascend-a2", "device": "ascend", "count": 16}
_MODEL = "GLM-4.5"
_ENGINE = "vllm-ascend"
_ENGINE_VERSION = "v0.18.0"


def _hw(tmp_path: Path) -> Path:
    p = tmp_path / "hardware_info.json"
    p.write_text(json.dumps(_HW), encoding="utf-8")
    return p


def _run_placeholder(config_root_real: Path, tmp_path: Path, monkeypatch):
    """无运行时上下文跑 MULTI_NODE 流水线(占位路径)。"""
    monkeypatch.setenv("ENGINE_VERSION", _ENGINE_VERSION)
    monkeypatch.setenv("WINGS_START_LOG", str(tmp_path / "wings_start.log"))
    return run_pipeline(
        PipelineRequest(
            target=Target(model_name=_MODEL, topology=Topology.MULTI_NODE, engine=_ENGINE),
            hardware_info_path=_hw(tmp_path),
            config_root=config_root_real,
            user_input=UserInput(cli_overrides={"port": 18000}),
        ),
        output_dir=tmp_path / "out",
    )


def _node_specs_with_rpc_port(rpc_port: object):
    strategy = {
        "head": {
            "engine_config": {"model": "demo/model", "data_parallel_rpc_port": rpc_port},
            "env": {},
        },
        "worker": {
            "engine_config": {"model": "demo/model", "data_parallel_rpc_port": rpc_port},
            "env": {},
        },
    }
    node_specs = normalize_nodes(strategy, "scenarios.multi_node.strategies.test", pod_count=2)
    assert node_specs is not None
    return node_specs


def _node_specs_with_data_parallel_address(recipe_address="$local_ip"):
    """构造声明 runtime-owned DP 地址的最小普通多机 recipe。"""
    strategy = {
        "head": {
            "engine_config": {
                "model": "demo/model",
                "tensor_parallel_size": 1,
                "data_parallel_size": 2,
                "data_parallel_size_local": 1,
                "data_parallel_start_rank": 0,
                "data_parallel_address": recipe_address,
            },
            "env": {},
        },
        "worker": {
            "engine_config": {
                "model": "demo/model",
                "tensor_parallel_size": 1,
                "data_parallel_size": 2,
                "data_parallel_size_local": 1,
                "data_parallel_start_rank": 1,
                "data_parallel_address": recipe_address,
            },
            "env": {},
        },
    }
    node_specs = normalize_nodes(strategy, "scenarios.multi_node.strategies.test", pod_count=2)
    assert node_specs is not None
    return node_specs


def _resolve_runtime_node(
    node_specs,
    *,
    feature_overrides=None,
    strategy_feature_inject_overrides=None,
    accel_overrides=None,
    user_layer=None,
):
    """用最小 runtime placement 调用普通 multi-node resolver。"""
    return _resolve_multi_node(
        node_specs,
        model_path="<test-model>",
        user_layer=user_layer or {},
        feature_overrides=feature_overrides or {},
        feature_trace_sources={},
        accel_overrides=accel_overrides or {},
        accel_env={},
        device_count=None,
        rank_ip="10.0.0.2",
        node_ips=["10.0.0.1", "10.0.0.2"],
        master_ip="10.0.0.1",
        strategy_feature_inject_overrides=strategy_feature_inject_overrides,
    )


@pytest.mark.parametrize(
    ("layer", "kwargs"),
    [
        ("strategy_feature", {"feature_overrides": {"data_parallel_address": "feature-host"}}),
        (
            "strategy_feature_inject",
            {"strategy_feature_inject_overrides": {"data_parallel_address": "feature-inject-host"}},
        ),
        ("strategy_accel", {"accel_overrides": {"data_parallel_address": "accel-host"}}),
        ("user_cli", {"user_layer": {"data_parallel_address": "user-host"}}),
    ],
)
def test_runtime_owned_data_parallel_address_rejects_later_layer_override(layer, kwargs):
    """验证已声明 DP 地址时，所有后续层的同名覆盖都 fail-fast。"""
    with pytest.raises(ValueError, match=rf"multi_node.*{layer}.*data_parallel_address"):
        _resolve_runtime_node(_node_specs_with_data_parallel_address(), **kwargs)


def test_undeclared_data_parallel_address_does_not_enable_ownership_check():
    """验证当前 recipe 未声明 DP 地址时不触发专项后续层冲突检查。"""
    engine_config_traces, *_ = _resolve_runtime_node(
        _node_specs_with_rpc_port(12321),
        feature_overrides={"data_parallel_address": "feature-host"},
    )

    assert engine_config_traces["data_parallel_address"].final_value == "feature-host"


def test_runtime_owned_data_parallel_address_uses_master_for_worker_local_token():
    """验证 worker 的 $local_ip 被 key-owned runtime 值覆盖为 MASTER_IP。"""
    engine_config_traces, *_ = _resolve_runtime_node(_node_specs_with_data_parallel_address())

    address = engine_config_traces["data_parallel_address"]
    assert address.final_value == "10.0.0.1"
    assert address.final_layer == "strategy_topology_inject"
    assert [event.value for event in address.events] == ["$local_ip", "10.0.0.1"]


@pytest.mark.parametrize("recipe_address", ["$LOCAL_IP", "$NODE0_IP", "$MASTER_IP_ADDRESS", "192.168.1.10"])
def test_runtime_owned_data_parallel_address_reaches_argv_as_master_ip(recipe_address):
    """验证未知 token 和旧字面地址均不能进入最终 argv。"""
    engine_config_traces, *_ = _resolve_runtime_node(
        _node_specs_with_data_parallel_address(recipe_address)
    )

    argv = build_argv(engine_config_traces, engine="vllm")
    address_index = argv.index("--data-parallel-address")
    assert argv[address_index + 1] == "10.0.0.1"
    assert recipe_address not in argv


@pytest.mark.parametrize(
    ("rank_ip", "node_ips", "master_ip"),
    [
        ("10.0.0.1", None, None),
        (None, ["10.0.0.1", "10.0.0.2"], None),
        (None, None, "10.0.0.1"),
    ],
)
def test_partial_runtime_placement_currently_keeps_placeholder_view(rank_ip, node_ips, master_ip):
    """验证不足以进入 runtime injection 的 partial placement 保持占位视图。"""
    engine_config_traces, _, _, nodes, notes = _resolve_multi_node(
        _node_specs_with_data_parallel_address(),
        model_path="<test-model>",
        user_layer={},
        feature_overrides={},
        feature_trace_sources={},
        accel_overrides={},
        accel_env={},
        device_count=None,
        rank_ip=rank_ip,
        node_ips=node_ips,
        master_ip=master_ip,
    )

    assert not engine_config_traces
    assert nodes is not None
    assert notes["multi_node_injection_status"] == "pending_runtime_context"


def test_runtime_placement_without_master_ip_fails_after_node_selection():
    """验证 RANK_IP 和 NODE_IPS 齐全但缺 MASTER_IP 时不能生成 owned 地址。"""
    with pytest.raises(ValueError, match="MASTER_IP"):
        _resolve_multi_node(
            _node_specs_with_data_parallel_address(),
            model_path="<test-model>",
            user_layer={},
            feature_overrides={},
            feature_trace_sources={},
            accel_overrides={},
            accel_env={},
            device_count=None,
            rank_ip="10.0.0.2",
            node_ips=["10.0.0.1", "10.0.0.2"],
            master_ip=None,
        )


def test_multi_node_accepts_numeric_data_parallel_rpc_port() -> None:
    _, _, _, nodes, _ = _resolve_multi_node(
        _node_specs_with_rpc_port(12321),
        model_path="<test-model>",
        user_layer={},
        feature_overrides={},
        feature_trace_sources={},
        accel_overrides={},
        accel_env={},
        device_count=None,
        rank_ip=None,
        node_ips=None,
        master_ip=None,
    )

    assert nodes is not None


def test_placeholder_per_node_deep_merge_and_literal_placeholders(config_root_real, tmp_path, monkeypatch):
    """验证无运行时上下文 → 两节点占位:深合并保嵌套 dict、$占位符字面、顶层留空。"""
    resolved, *_ = _run_placeholder(config_root_real, tmp_path, monkeypatch)
    assert resolved.topology is Topology.MULTI_NODE
    assert not resolved.engine_config_traces and not resolved.env_traces
    assert resolved.nodes is not None
    assert [n.role for n in resolved.nodes] == ["head", "worker"]

    head = resolved.nodes[0]
    cc = head.engine_config_traces["compilation_config"].final_value
    assert isinstance(cc, dict) and "cudagraph_mode" in cc          # 深合并保嵌套
    assert head.engine_config_traces["data_parallel_address"].final_value == "$local_ip"  # 字面保留
    assert head.engine_config_traces["port"].final_value == 18000   # user_cli 应用到每节点
    assert resolved.nodes[1].engine_config_traces["data_parallel_address"].final_value == "$node0_ip"


def test_placeholder_start_command_non_executable(config_root_real, tmp_path, monkeypatch):
    """验证占位 start_command.sh:无 exec、exit 3 阻断、含字面占位、repro 同为占位。"""
    _, start_path, repro_path, _ = _run_placeholder(config_root_real, tmp_path, monkeypatch)
    text = start_path.read_text(encoding="utf-8")
    assert "RUNTIME INJECTION PENDING" in text and "exit 3" in text
    assert "\nexec " not in text and not text.startswith("exec ")
    assert "$local_ip" in text and "$node0_ip" in text
    assert "RUNTIME INJECTION PENDING" in repro_path.read_text(encoding="utf-8")


def test_placeholder_audit_has_nodes(config_root_real, tmp_path, monkeypatch):
    """验证占位 audit:顶层 engine_config 空 + nodes 数组 + pending 状态。"""
    _, _, _, audit_path = _run_placeholder(config_root_real, tmp_path, monkeypatch)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["engine_config"] == {}
    assert audit["multi_node_injection_status"] == "pending_runtime_context"
    assert len(audit["nodes"]) == 2
    assert audit["nodes"][0]["role"] == "head"
    assert audit["nodes"][0]["engine_config"]["data_parallel_address"]["final_value"] == "$local_ip"


def test_pd_topology_requires_pd_input(config_root_real, tmp_path, monkeypatch):
    """验证 PD 分离拓扑缺规范化 pd_input 时 fail-fast(ValueError,而非静默走 standard)。"""
    monkeypatch.setenv("ENGINE_VERSION", _ENGINE_VERSION)
    hardware = resolve_hardware(_hw(tmp_path))
    ev = resolve_engine_version(config_root_real, hardware.hardware_family, engine=_ENGINE)
    with pytest.raises(ValueError, match="pd_input"):
        resolve_config(
            ResolvedEnv(config_root=config_root_real, hardware=hardware, engine_version=ev),
            Target(model_name=_MODEL, topology=Topology.PD_PREFILL, engine=_ENGINE),
        )
