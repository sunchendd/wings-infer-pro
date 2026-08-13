"""PD ``pd_disaggregation.nodes[]`` recipe 选择与归一化。"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict

from wings_ctl.core.constants import DEFAULT_ENGINE_PORT
from wings_ctl.core.models import (
    ConnectorProfile,
    KvPortPolicy,
    ParallelShape,
    PD_DP_LAUNCH_EXTERNAL_RANK,
    PD_DP_LAUNCH_NONE,
    PD_ENDPOINT_PER_PROCESS,
    PD_ENGINE_ID_FROM_INDEX,
    PD_ENGINE_ID_OMIT,
    PD_KV_LISTENER_DEVICE_COUNT_PLUS_ONE,
    PD_KV_PORT_FROM_INDEX,
    PD_LISTENER_OWNER_PER_POD_CONNECTOR_GROUP,
    PD_PROCESS_LAYOUT_PER_LOCAL_RANK,
    PD_PROCESS_LAYOUT_SINGLE,
    PD_TOPOLOGY_DERIVED_1P1D,
    PD_TOPOLOGY_EXPLICIT_ALLOCATION,
    PdEngineIdPolicy,
    PdRole,
    PdRuntimeSpec,
    PdTopologyInputPolicy,
)
from wings_ctl.core.topology import Topology

logger = logging.getLogger(__name__)

_ALLOWED_INPUT_POLICIES = {
    PD_TOPOLOGY_DERIVED_1P1D,
    PD_TOPOLOGY_EXPLICIT_ALLOCATION,
}
_ROLE_NAMES = {"prefill": PdRole.PREFILL, "decode": PdRole.DECODE}
_RUNTIME_OWNED_ENGINE_FIELDS = {
    "port",
    "data_parallel_size",
    "data_parallel_rank",
    "data_parallel_start_rank",
    "data_parallel_size_local",
    "data_parallel_address",
    "data_parallel_rpc_port",
    "data_parallel_external_lb",
    "tensor_parallel_size",
}


@dataclass(frozen=True)
class PdRoleRecipe:
    """一个 role 从 nodes recipe 归一化后的静态配置与执行元数据。"""

    role: PdRole
    topology: Topology
    strategy_name: str
    source_prefix: str
    engine_config: Dict[str, Any]
    env: Dict[str, Any]
    runtime: PdRuntimeSpec


@dataclass(frozen=True)
class _NormalizedNode:
    """移除 runtime-owned 字段后的单个 recipe node。"""

    role: PdRole
    index: int
    source_prefix: str
    engine_config: Dict[str, Any]
    env: Dict[str, Any]
    prefill_shape: ParallelShape
    decode_shape: ParallelShape
    connector_name: str
    rpc_port: int | None
    kv_port: int
    engine_id: int | None


@dataclass(frozen=True)
class _IdentityProfile:
    """从所有 P/D node identity 推导出的全局 Instance profile。"""

    engine_id_policy: PdEngineIdPolicy
    kv_base: int
    kv_stride: int


def _required_mapping(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"PD recipe {path} 必须是 mapping。")
    return value


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"PD recipe {path} 必须是正整数，当前值为 {value!r}。")
    return value


def _port(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ValueError(
            f"PD recipe {path} 必须写入 1..65535 的实际端口，不能保留 $6 等脚本占位符，当前值为 {value!r}。"
        )
    return value


def _parallel_shape(data: Any, path: str) -> ParallelShape:
    shape = _required_mapping(data, path)
    return ParallelShape(
        dp_size=_positive_int(shape.get("dp_size"), f"{path}.dp_size"),
        tp_size=_positive_int(shape.get("tp_size"), f"{path}.tp_size"),
    )


def _select_strategy(model_data: Dict[str, Any]) -> tuple[str, str, Dict[str, Any]]:
    """选择唯一的 ``scenarios.pd_disaggregation`` 默认 strategy。"""
    scenario_path = "scenarios.pd_disaggregation"
    scenarios = _required_mapping(model_data.get("scenarios"), "scenarios")
    scenario = _required_mapping(scenarios.get("pd_disaggregation"), scenario_path)
    strategies = _required_mapping(scenario.get("strategies"), f"{scenario_path}.strategies")
    defaults = [
        name
        for name, strategy in strategies.items()
        if isinstance(strategy, dict) and strategy.get("default_strategy") is True
    ]
    if len(defaults) != 1:
        raise ValueError(
            f"PD recipe {scenario_path}.strategies 必须恰好一个 default_strategy=true，当前为 {defaults}。"
        )
    name = defaults[0]
    prefix = f"{scenario_path}.strategies.{name}"
    return name, prefix, _required_mapping(strategies[name], prefix)


def _normalize_node(raw: Any, path: str, expected_index: int) -> _NormalizedNode:
    """解析一个 node，并把动态参数从静态 engine config 中剥离。"""
    node = _required_mapping(raw, path)
    role_name = node.get("role")
    if role_name not in _ROLE_NAMES:
        raise ValueError(f"PD recipe {path}.role 必须是 'prefill' 或 'decode'，当前为 {role_name!r}。")
    role = _ROLE_NAMES[role_name]
    index = node.get("index")
    if index != expected_index:
        raise ValueError(f"PD recipe {path}.index 必须按 role 从 0 连续递增，期望 {expected_index}，当前 {index!r}。")

    config_path = f"{path}.engine_config"
    config = deepcopy(_required_mapping(node.get("engine_config"), config_path))
    rpc_port_raw = config.get("data_parallel_rpc_port")
    rpc_port = _port(rpc_port_raw, f"{config_path}.data_parallel_rpc_port") if rpc_port_raw is not None else None
    transfer_path = f"{config_path}.kv_transfer_config"
    transfer = deepcopy(_required_mapping(config.get("kv_transfer_config"), transfer_path))
    connector_name = transfer.get("kv_connector")
    if not isinstance(connector_name, str) or not connector_name.strip():
        raise ValueError(f"PD recipe {transfer_path}.kv_connector 必须是非空字符串。")
    expected_kv_role = "kv_producer" if role is PdRole.PREFILL else "kv_consumer"
    if transfer.get("kv_role") != expected_kv_role:
        raise ValueError(
            f"PD recipe {transfer_path}.kv_role 必须是 {expected_kv_role!r}，当前为 {transfer.get('kv_role')!r}。"
        )
    kv_port = _port(transfer.get("kv_port"), f"{transfer_path}.kv_port")
    engine_id_raw = transfer.get("engine_id")
    if engine_id_raw is None:
        engine_id = None
    elif isinstance(engine_id_raw, bool) or not isinstance(engine_id_raw, (int, str)):
        raise ValueError(f"PD recipe {transfer_path}.engine_id 必须是非负整数或省略。")
    else:
        try:
            engine_id = int(engine_id_raw)
        except ValueError as exc:
            raise ValueError(f"PD recipe {transfer_path}.engine_id 必须是非负整数，当前为 {engine_id_raw!r}。") from exc
        if engine_id < 0:
            raise ValueError(f"PD recipe {transfer_path}.engine_id 必须是非负整数，当前为 {engine_id_raw!r}。")

    extra_path = f"{transfer_path}.kv_connector_extra_config"
    extra = deepcopy(_required_mapping(transfer.get("kv_connector_extra_config"), extra_path))
    prefill_shape = _parallel_shape(extra.pop("prefill", None), f"{extra_path}.prefill")
    decode_shape = _parallel_shape(extra.pop("decode", None), f"{extra_path}.decode")
    configured_tp = config.get("tensor_parallel_size")
    role_shape = prefill_shape if role is PdRole.PREFILL else decode_shape
    if configured_tp not in ("$7", role_shape.tp_size):
        raise ValueError(
            f"PD recipe {config_path}.tensor_parallel_size 必须是 $7 或当前 role TP={role_shape.tp_size}，"
            f"当前为 {configured_tp!r}。"
        )

    for field in _RUNTIME_OWNED_ENGINE_FIELDS:
        config.pop(field, None)
    transfer.pop("kv_port", None)
    transfer.pop("engine_id", None)
    if extra:
        transfer["kv_connector_extra_config"] = extra
    else:
        transfer.pop("kv_connector_extra_config", None)
    config["tensor_parallel_size"] = role_shape.tp_size
    config["kv_transfer_config"] = transfer

    env = deepcopy(_required_mapping(node.get("env", {}), f"{path}.env"))
    return _NormalizedNode(
        role=role,
        index=index,
        source_prefix=path,
        engine_config=config,
        env=env,
        prefill_shape=prefill_shape,
        decode_shape=decode_shape,
        connector_name=connector_name.strip(),
        rpc_port=rpc_port,
        kv_port=kv_port,
        engine_id=engine_id,
    )


def _normalize_nodes(strategy: Dict[str, Any], prefix: str) -> Dict[PdRole, list[_NormalizedNode]]:
    nodes = strategy.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError(f"PD recipe {prefix}.nodes 必须是非空列表。")
    grouped: Dict[PdRole, list[_NormalizedNode]] = {PdRole.PREFILL: [], PdRole.DECODE: []}
    for position, raw in enumerate(nodes):
        role_name = raw.get("role") if isinstance(raw, dict) else None
        role = _ROLE_NAMES.get(role_name)
        expected_index = len(grouped[role]) if role is not None else 0
        node = _normalize_node(raw, f"{prefix}.nodes[{position}]", expected_index)
        grouped[node.role].append(node)
    for role, role_nodes in grouped.items():
        if not role_nodes:
            raise ValueError(f"PD recipe {prefix}.nodes 缺少 role={role.value} 的节点。")
    return grouped


def _identity_groups(nodes: list[_NormalizedNode]) -> list[tuple[tuple[int | None, int], int]]:
    """按 recipe 顺序聚合同一 logical Instance 的连续成员。"""
    groups: list[tuple[tuple[int | None, int], int]] = []
    seen: set[tuple[int | None, int]] = set()
    for node in nodes:
        identity = (node.engine_id, node.kv_port)
        if groups and groups[-1][0] == identity:
            previous, count = groups[-1]
            groups[-1] = (previous, count + 1)
            continue
        if identity in seen:
            raise ValueError(f"PD recipe logical Instance identity {identity!r} 的成员必须连续排列。")
        seen.add(identity)
        groups.append((identity, 1))
    member_counts = {count for _, count in groups}
    if len(member_counts) != 1:
        raise ValueError(
            f"PD recipe 同一 role 的 logical Instance 成员 Pod 数必须一致，当前为 {sorted(member_counts)}。"
        )
    return groups


def _derive_identity_profile(grouped: Dict[PdRole, list[_NormalizedNode]]) -> _IdentityProfile:
    """验证 P 在前 D 在后的全局 Instance identity 和 KV port 等差规则。"""
    groups = _identity_groups(grouped[PdRole.PREFILL]) + _identity_groups(grouped[PdRole.DECODE])
    identities = [identity for identity, _ in groups]
    engine_ids = [engine_id for (engine_id, _) in identities]
    if all(engine_id is None for engine_id in engine_ids):
        engine_id_policy = PD_ENGINE_ID_OMIT
    elif all(engine_id is not None for engine_id in engine_ids):
        expected = list(range(len(engine_ids)))
        if engine_ids != expected:
            raise ValueError(
                "PD recipe engine_id 必须按 logical Instance 以 P 在前、D 在后的顺序从 0 连续递增，"
                f"当前为 {engine_ids}。"
            )
        engine_id_policy = PD_ENGINE_ID_FROM_INDEX
    else:
        raise ValueError("PD recipe P/D node 的 engine_id 必须全部省略或全部显式声明。")

    ports = [kv_port for (_, kv_port) in identities]
    if len(set(ports)) != len(ports):
        raise ValueError(f"PD recipe 不同 logical Instance 的 kv_port 必须唯一，当前为 {ports}。")
    strides = [right - left for left, right in zip(ports, ports[1:])]
    if not strides or strides[0] <= 0 or any(stride != strides[0] for stride in strides):
        raise ValueError(f"PD recipe kv_port 必须按 logical Instance 使用正等差序列，当前为 {ports}。")
    return _IdentityProfile(engine_id_policy, ports[0], strides[0])


def _validate_role_nodes(nodes: list[_NormalizedNode], role: PdRole) -> _NormalizedNode:
    """确保一个 role 的所有节点仅 runtime-owned 字段不同。"""
    first = nodes[0]
    for node in nodes[1:]:
        if node.engine_config != first.engine_config:
            raise ValueError(f"PD recipe role={role.value} 的节点静态 engine_config 不一致：{node.source_prefix}。")
        if node.env != first.env:
            raise ValueError(f"PD recipe role={role.value} 的节点 env 不一致：{node.source_prefix}。")
        if (node.prefill_shape, node.decode_shape) != (first.prefill_shape, first.decode_shape):
            raise ValueError(f"PD recipe role={role.value} 的节点 P/D shape 不一致：{node.source_prefix}。")
        if node.connector_name != first.connector_name or node.rpc_port != first.rpc_port:
            raise ValueError(f"PD recipe role={role.value} 的 connector 或 DP RPC 端口不一致：{node.source_prefix}。")
    return first


def select_pd_recipe_pair(
    model_data: Dict[str, Any], topology_input_policy: PdTopologyInputPolicy
) -> Dict[PdRole, PdRoleRecipe]:
    """从正式 ``pd_disaggregation.nodes[]`` recipe 生成内部 P/D role pair。

    外部 YAML 保留官方命令可直接表达的参数；rank、local DP、backend port、placement 和
    connector identity 在此被识别为 runtime-owned，后续由 planner 以 MaaS 输入派生。
    """
    if topology_input_policy not in _ALLOWED_INPUT_POLICIES:
        raise ValueError(f"未知 PD topology input policy：{topology_input_policy!r}。")
    strategy_name, prefix, strategy = _select_strategy(model_data)
    grouped = _normalize_nodes(strategy, prefix)
    first = {role: _validate_role_nodes(nodes, role) for role, nodes in grouped.items()}
    if (
        first[PdRole.PREFILL].prefill_shape != first[PdRole.DECODE].prefill_shape
        or first[PdRole.PREFILL].decode_shape != first[PdRole.DECODE].decode_shape
    ):
        raise ValueError("PD recipe P/D 节点必须描述同一份 P/D parallel shape。")
    identity = _derive_identity_profile(grouped)
    shape_policy = (
        PD_TOPOLOGY_DERIVED_1P1D
        if first[PdRole.PREFILL].prefill_shape.dp_size == 1 and first[PdRole.PREFILL].decode_shape.dp_size == 1
        else PD_TOPOLOGY_EXPLICIT_ALLOCATION
    )
    if topology_input_policy != shape_policy:
        raise ValueError(f"PD recipe 只接受 {shape_policy!r}，当前输入为 {topology_input_policy!r}。")
    if shape_policy == PD_TOPOLOGY_EXPLICIT_ALLOCATION:
        missing_rpc_roles = [role.value for role, node in first.items() if node.rpc_port is None]
        if missing_rpc_roles:
            raise ValueError(f"PD explicit_allocation recipe 缺少实际 DP RPC 端口：roles={missing_rpc_roles}。")
    pair: Dict[PdRole, PdRoleRecipe] = {}
    for role, topology in ((PdRole.PREFILL, Topology.PD_PREFILL), (PdRole.DECODE, Topology.PD_DECODE)):
        node = first[role]
        ordinary_1p1d = shape_policy == PD_TOPOLOGY_DERIVED_1P1D
        runtime = PdRuntimeSpec(
            topology_input_policy=shape_policy,
            prefill_shape=node.prefill_shape,
            decode_shape=node.decode_shape,
            instance_member_count=_identity_groups(grouped[role])[0][1],
            process_layout=PD_PROCESS_LAYOUT_SINGLE if ordinary_1p1d else PD_PROCESS_LAYOUT_PER_LOCAL_RANK,
            dp_launch_policy=PD_DP_LAUNCH_NONE if ordinary_1p1d else PD_DP_LAUNCH_EXTERNAL_RANK,
            endpoint_policy=PD_ENDPOINT_PER_PROCESS,
            backend_port_base=DEFAULT_ENGINE_PORT,
            data_parallel_rpc_port=None if ordinary_1p1d else node.rpc_port,
            connector_profile=ConnectorProfile(
                connector_name=node.connector_name,
                engine_id_policy=identity.engine_id_policy,
                kv_port_policy=KvPortPolicy(
                    mode=PD_KV_PORT_FROM_INDEX,
                    base=identity.kv_base,
                    instance_stride=identity.kv_stride,
                    process_stride=0,
                    listener_span=PD_KV_LISTENER_DEVICE_COUNT_PLUS_ONE,
                ),
                listener_owner_scope=PD_LISTENER_OWNER_PER_POD_CONNECTOR_GROUP,
            ),
        )
        pair[role] = PdRoleRecipe(
            role=role,
            topology=topology,
            strategy_name=strategy_name,
            source_prefix=node.source_prefix,
            engine_config=node.engine_config,
            env=node.env,
            runtime=runtime,
        )
    logger.info(
        "PD nodes recipe selected: policy=%s strategy=%s prefill_node=%s decode_node=%s",
        topology_input_policy,
        strategy_name,
        pair[PdRole.PREFILL].source_prefix,
        pair[PdRole.DECODE].source_prefix,
    )
    return pair
