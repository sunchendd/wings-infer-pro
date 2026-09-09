"""PD ``pd_disaggregation.nodes[]`` 归一化与强校验测试。"""

from __future__ import annotations

from copy import deepcopy

import pytest

from wings_ctl.core.models import PdRole
from wings_ctl.pd.recipe import select_pd_recipe_pair


def _node(
    role: str,
    index: int,
    *,
    prefill_dp: int = 2,
    prefill_tp: int = 4,
    decode_dp: int = 4,
    decode_tp: int = 2,
    rpc_port: int | str | None = None,
    kv_port: int | None = None,
    engine_id: int | None = None,
) -> dict:
    """构造一个与上游 v0.23.0 资产同形的 node。"""
    is_prefill = role == "prefill"
    transfer = {
        "kv_connector": "MooncakeConnectorV1",
        "kv_role": "kv_producer" if is_prefill else "kv_consumer",
        "kv_port": kv_port if kv_port is not None else (36000 if is_prefill else 36100),
        "kv_connector_extra_config": {
            "use_ascend_direct": True,
            "prefill": {"dp_size": prefill_dp, "tp_size": prefill_tp},
            "decode": {"dp_size": decode_dp, "tp_size": decode_tp},
        },
    }
    if engine_id is not None:
        transfer["engine_id"] = engine_id
    return {
        "role": role,
        "index": index,
        "engine_config": {
            "model": "synthetic/model",
            "host": "0.0.0.0",
            "port": "$2",
            "data_parallel_size": "$3",
            "data_parallel_rank": "$4",
            "data_parallel_address": "$5",
            "data_parallel_rpc_port": rpc_port if rpc_port is not None else (10521 if is_prefill else 10523),
            "tensor_parallel_size": "$7",
            "enable_expert_parallel": True,
            "kv_transfer_config": transfer,
        },
        "env": {
            "HCCL_IF_IP": "$local_ip",
            "HCCL_SOCKET_IFNAME": "$nic_name",
        },
        "system_setup": {"commands": ["untrusted legacy example is intentionally ignored"]},
    }


def _model(
    *,
    prefill_nodes: int = 2,
    decode_nodes: int = 2,
    prefill_dp: int = 2,
    prefill_tp: int = 4,
    decode_dp: int = 4,
    decode_tp: int = 2,
    with_engine_id: bool = False,
) -> dict:
    """构造包含一个 P Instance 和一个 D Instance 的正式 nodes recipe。"""
    nodes = []
    for role, count, kv_port, engine_id in (
        ("prefill", prefill_nodes, 36000, 0),
        ("decode", decode_nodes, 36100, 1),
    ):
        for index in range(count):
            nodes.append(
                _node(
                    role,
                    index,
                    prefill_dp=prefill_dp,
                    prefill_tp=prefill_tp,
                    decode_dp=decode_dp,
                    decode_tp=decode_tp,
                    kv_port=kv_port,
                    engine_id=engine_id if with_engine_id else None,
                )
            )
    return {
        "scenarios": {
            "pd_disaggregation": {
                "strategies": {
                    "pd_cluster": {
                        "default_strategy": True,
                        "nodes": nodes,
                    }
                }
            }
        }
    }


def test_select_pd_recipe_pair_normalizes_nodes_without_duplicate_runtime_schema() -> None:
    """验证 nodes 直接归一化，YAML 不再要求 pd_prefill/pd_decode/pd_runtime。"""
    pair = select_pd_recipe_pair(_model(), "explicit_allocation")

    assert set(pair) == {PdRole.PREFILL, PdRole.DECODE}
    prefill = pair[PdRole.PREFILL]
    decode = pair[PdRole.DECODE]
    assert prefill.runtime.prefill_shape.dp_size == 2
    assert decode.runtime.decode_shape.dp_size == 4
    assert prefill.runtime.instance_member_count == 2
    assert decode.runtime.instance_member_count == 2
    assert prefill.runtime.data_parallel_rpc_port == 10521
    assert decode.runtime.data_parallel_rpc_port == 10523
    assert prefill.runtime.connector_profile.kv_port_policy.base == 36000
    assert prefill.runtime.connector_profile.kv_port_policy.instance_stride == 100
    assert "port" not in prefill.engine_config
    assert "data_parallel_rank" not in prefill.engine_config
    assert "kv_port" not in prefill.engine_config["kv_transfer_config"]
    assert prefill.engine_config["tensor_parallel_size"] == 4


def test_select_pd_recipe_pair_preserves_role_system_setup() -> None:
    """PD role recipe 保留 system_setup，供当前 Pod 启动脚本执行安全 source 命令。"""
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    for node in nodes:
        node["system_setup"] = {"commands": ["source /dev/null"]}

    pair = select_pd_recipe_pair(model, "explicit_allocation")

    assert pair[PdRole.PREFILL].system_setup == {"commands": ["source /dev/null"]}
    assert pair[PdRole.DECODE].system_setup == {"commands": ["source /dev/null"]}


def test_select_pd_recipe_pair_ignores_non_source_system_setup_drift() -> None:
    """同一 role 的普通 commands、sysctl 和 sysfs 差异不会阻断 PD 解析。"""
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    nodes[0]["system_setup"] = {"commands": ['nic_name="eth0"'], "sysctls": {"vm.swappiness": 0}}
    nodes[1]["system_setup"] = {
        "commands": ['local_ip="10.0.0.1"'],
        "sysfs_writes": [{"path": "/sys/test", "value": "1"}],
    }

    pair = select_pd_recipe_pair(model, "explicit_allocation")

    assert pair[PdRole.PREFILL].system_setup == nodes[0]["system_setup"]


def test_select_pd_recipe_pair_rejects_source_command_drift() -> None:
    """同一 role 的可执行 source 环境初始化命令必须一致。"""
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    nodes[0]["system_setup"] = {"commands": ["source /dev/null"]}
    nodes[1]["system_setup"] = {"commands": ["source /etc/profile"]}

    with pytest.raises(ValueError, match="inconsistent source commands"):
        select_pd_recipe_pair(model, "explicit_allocation")


def test_select_pd_recipe_pair_accepts_global_engine_identity_sequence() -> None:
    """验证显式 connector identity 被归一化为 PD_INDEX 派生策略。"""
    pair = select_pd_recipe_pair(_model(with_engine_id=True), "explicit_allocation")

    profile = pair[PdRole.DECODE].runtime.connector_profile
    assert profile.engine_id_policy == "from_pd_index"
    assert "engine_id" not in pair[PdRole.DECODE].engine_config["kv_transfer_config"]


def test_select_pd_recipe_pair_accepts_a2_four_p_instances_one_four_pod_d() -> None:
    """验证 4*1P + 1*4D 的 identity 分组可无损表达。"""
    model = _model(prefill_nodes=1, decode_nodes=4, prefill_dp=8, prefill_tp=1, decode_dp=32, decode_tp=1)
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    prefill_template = nodes[0]
    nodes[:1] = []
    for index in range(4):
        node = deepcopy(prefill_template)
        node["index"] = index
        node["engine_config"]["kv_transfer_config"]["engine_id"] = index
        node["engine_config"]["kv_transfer_config"]["kv_port"] = 30000 + index * 100
        nodes.insert(index, node)
    for node in nodes[4:]:
        node["engine_config"]["kv_transfer_config"]["engine_id"] = 4
        node["engine_config"]["kv_transfer_config"]["kv_port"] = 30400

    pair = select_pd_recipe_pair(model, "explicit_allocation")

    assert pair[PdRole.PREFILL].runtime.instance_member_count == 1
    assert pair[PdRole.DECODE].runtime.instance_member_count == 4
    assert pair[PdRole.DECODE].runtime.connector_profile.kv_port_policy.base == 30000


def test_select_pd_recipe_pair_exposes_a2_wrong_d_identity_as_four_singletons() -> None:
    """验证错误 identity 会形成四个 singleton，运行时与四成员 NODE_IPS 冲突。"""
    model = _model(prefill_nodes=1, decode_nodes=4, prefill_dp=8, prefill_tp=1, decode_dp=32, decode_tp=1)
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    for global_index, node in enumerate(nodes):
        node["engine_config"]["kv_transfer_config"]["engine_id"] = global_index
        node["engine_config"]["kv_transfer_config"]["kv_port"] = 30000 + global_index * 100

    pair = select_pd_recipe_pair(model, "explicit_allocation")

    assert pair[PdRole.DECODE].runtime.instance_member_count == 1


def test_select_pd_recipe_pair_rejects_rpc_placeholder() -> None:
    """验证 $6 只表示官方 shell 形参，不能冒充可执行端口。"""
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    nodes[0]["engine_config"]["data_parallel_rpc_port"] = "$6"

    with pytest.raises(ValueError, match=r"integer port.*\$6"):
        select_pd_recipe_pair(model, "explicit_allocation")


def test_select_pd_recipe_pair_rejects_quoted_numeric_rpc_port() -> None:
    """验证 YAML 中带引号的数字不是可执行的整数端口。"""
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    nodes[0]["engine_config"]["data_parallel_rpc_port"] = "12321"

    with pytest.raises(ValueError, match=r"integer port.*'12321'"):
        select_pd_recipe_pair(model, "explicit_allocation")


def test_select_pd_recipe_pair_rejects_wrong_input_policy() -> None:
    """验证非 1P1D recipe 必须使用 MaaS 六字段显式 allocation。"""
    with pytest.raises(ValueError, match="explicit_allocation"):
        select_pd_recipe_pair(_model(), "derived_1p1d")


def test_select_pd_recipe_pair_derives_ordinary_1p1d_policy() -> None:
    """验证 P/D DP 都为 1 时使用单进程且不启动 DP。"""
    pair = select_pd_recipe_pair(
        _model(prefill_nodes=1, decode_nodes=1, prefill_dp=1, decode_dp=1),
        "derived_1p1d",
    )

    runtime = pair[PdRole.PREFILL].runtime
    assert runtime.topology_input_policy == "derived_1p1d"
    assert runtime.process_layout == "single_process"
    assert runtime.dp_launch_policy == "none"
    assert runtime.data_parallel_rpc_port is None


def test_select_pd_recipe_pair_allows_ordinary_recipe_without_rpc_port() -> None:
    """验证普通 DP1 recipe 不必声明不会消费的 DP RPC 端口。"""
    model = _model(prefill_nodes=1, decode_nodes=1, prefill_dp=1, decode_dp=1)
    for node in model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]:
        node["engine_config"].pop("data_parallel_rpc_port")

    pair = select_pd_recipe_pair(model, "derived_1p1d")

    assert all(recipe.runtime.data_parallel_rpc_port is None for recipe in pair.values())


def test_select_pd_recipe_pair_requires_rpc_port_for_explicit_allocation() -> None:
    """验证场景 B 仍要求每个 role 提供实际 DP RPC 端口。"""
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    for node in nodes:
        node["engine_config"].pop("data_parallel_rpc_port")

    with pytest.raises(ValueError, match="missing concrete DP RPC"):
        select_pd_recipe_pair(model, "explicit_allocation")


def test_select_pd_recipe_pair_requires_exactly_one_default() -> None:
    model = _model()
    model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["default_strategy"] = False

    with pytest.raises(ValueError, match="exactly one"):
        select_pd_recipe_pair(model, "explicit_allocation")


def test_select_pd_recipe_pair_rejects_missing_role() -> None:
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"] = [
        node for node in nodes if node["role"] == "prefill"
    ]

    with pytest.raises(ValueError, match="role=D"):
        select_pd_recipe_pair(model, "explicit_allocation")


def test_select_pd_recipe_pair_rejects_role_static_config_drift() -> None:
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    nodes[1]["engine_config"]["max_model_len"] = 123

    with pytest.raises(ValueError, match="inconsistent static engine_config"):
        select_pd_recipe_pair(model, "explicit_allocation")


def test_select_pd_recipe_pair_rejects_wrong_kv_role() -> None:
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    nodes[0]["engine_config"]["kv_transfer_config"]["kv_role"] = "kv_consumer"

    with pytest.raises(ValueError, match="kv_producer"):
        select_pd_recipe_pair(model, "explicit_allocation")


def test_select_pd_recipe_pair_rejects_role_shape_mismatch() -> None:
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    nodes[-1]["engine_config"]["kv_transfer_config"]["kv_connector_extra_config"]["decode"]["dp_size"] = 8

    with pytest.raises(ValueError, match="inconsistent P/D shape"):
        select_pd_recipe_pair(model, "explicit_allocation")


def test_select_pd_recipe_pair_rejects_mixed_engine_id_policy() -> None:
    model = _model()
    nodes = model["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]["nodes"]
    for node in nodes[:2]:
        node["engine_config"]["kv_transfer_config"]["engine_id"] = 0

    with pytest.raises(ValueError, match="all omitted or all explicit"):
        select_pd_recipe_pair(model, "explicit_allocation")
