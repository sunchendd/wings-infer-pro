"""PD ``pd_disaggregation.nodes[]`` recipe 选择与归一化。"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict

from wings_ctl.core.constants import DEFAULT_ENGINE_PORT
from wings_ctl.core.system_setup import extract_source_commands
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
    system_setup: Dict[str, Any] | None
    source_commands: list[str]
    runtime: PdRuntimeSpec


@dataclass(frozen=True)
class _NormalizedNode:
    """移除 runtime-owned 字段后的单个 recipe node。"""

    role: PdRole
    index: int
    source_prefix: str
    engine_config: Dict[str, Any]
    env: Dict[str, Any]
    system_setup: Dict[str, Any] | None
    source_commands: list[str]
    prefill_shape: ParallelShape
    decode_shape: ParallelShape
    connector_name: str
    rpc_port: int | None
    backend_port_base: int
    data_parallel_external_lb: bool
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
        raise ValueError(f"PD recipe {path} must be a mapping")
    return value


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"PD recipe {path} must be a positive integer; got {value!r}")
    return value


def _is_non_negative_int(value: Any) -> bool:
    """判断值是否为非布尔类型的非负整数。"""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _port(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ValueError(
            f"PD recipe {path} must contain an integer port in 1..65535, not a script placeholder; got {value!r}"
        )
    return value


def _parallel_shape(data: Any, path: str) -> ParallelShape:
    shape = _required_mapping(data, path)
    return ParallelShape(
        dp_size=_positive_int(shape.get("dp_size"), f"{path}.dp_size"),
        tp_size=_positive_int(shape.get("tp_size"), f"{path}.tp_size"),
    )


def _normalize_multi_connector(
    transfer: Dict[str, Any],
    transfer_path: str,
    expected_kv_role: str,
) -> tuple[Dict[str, Any], int]:
    """提取 MultiConnector 中的 Mooncake 参数并移除运行时生成的 lookup 端口。"""
    outer_extra_path = f"{transfer_path}.kv_connector_extra_config"
    outer_extra = _required_mapping(transfer.get("kv_connector_extra_config"), outer_extra_path)
    connectors = outer_extra.get("connectors")
    if not isinstance(connectors, list) or not connectors:
        raise ValueError(f"PD recipe {outer_extra_path}.connectors must be a non-empty list")
    mooncake = [
        (index, item)
        for index, item in enumerate(connectors)
        if isinstance(item, dict) and item.get("kv_connector") == "MooncakeConnectorV1"
    ]
    if len(mooncake) != 1:
        raise ValueError(f"PD recipe {outer_extra_path}.connectors must contain exactly one MooncakeConnectorV1")
    mooncake_index, mooncake_cfg = mooncake[0]
    mooncake_path = f"{outer_extra_path}.connectors[{mooncake_index}]"
    if mooncake_cfg.get("kv_role") != expected_kv_role:
        raise ValueError(
            f"PD recipe {mooncake_path}.kv_role must be {expected_kv_role!r}; got {mooncake_cfg.get('kv_role')!r}"
        )
    kv_port = _port(mooncake_cfg.get("kv_port"), f"{mooncake_path}.kv_port")
    transport_extra_path = f"{mooncake_path}.kv_connector_extra_config"
    transport_extra = deepcopy(_required_mapping(mooncake_cfg.get("kv_connector_extra_config"), transport_extra_path))

    normalized_connectors = deepcopy(connectors)
    for index, store in enumerate(normalized_connectors):
        if not isinstance(store, dict) or store.get("kv_connector") != "AscendStoreConnector":
            continue
        store_path = f"{outer_extra_path}.connectors[{index}]"
        if store.get("kv_role") != expected_kv_role:
            raise ValueError(
                f"PD recipe {store_path}.kv_role must be {expected_kv_role!r}; got {store.get('kv_role')!r}"
            )
        store_extra = _required_mapping(
            store.get("kv_connector_extra_config"), f"{store_path}.kv_connector_extra_config"
        )
        raw_lookup = store_extra.pop("lookup_rpc_port", None)
        if raw_lookup is not None and not _is_non_negative_int(raw_lookup):
            raise ValueError(
                f"PD recipe {store_path}.kv_connector_extra_config.lookup_rpc_port must be a non-negative integer"
            )

    normalized_outer = deepcopy(outer_extra)
    normalized_outer["connectors"] = normalized_connectors
    transfer["kv_connector_extra_config"] = normalized_outer
    return transport_extra, kv_port


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
            f"PD recipe {scenario_path}.strategies must contain exactly one default_strategy=true; got {defaults}"
        )
    name = defaults[0]
    prefix = f"{scenario_path}.strategies.{name}"
    return name, prefix, _required_mapping(strategies[name], prefix)


def _normalize_node(raw: Any, path: str, expected_index: int) -> _NormalizedNode:
    """解析一个 node，并把动态参数从静态 engine config 中剥离。"""
    node = _required_mapping(raw, path)
    role_name = node.get("role")
    if role_name not in _ROLE_NAMES:
        raise ValueError(f"PD recipe {path}.role must be 'prefill' or 'decode'; got {role_name!r}")
    role = _ROLE_NAMES[role_name]
    index = node.get("index")
    if index != expected_index:
        raise ValueError(
            f"PD recipe {path}.index must increase from 0 within its role; expected {expected_index}, got {index!r}"
        )

    config_path = f"{path}.engine_config"
    config = deepcopy(_required_mapping(node.get("engine_config"), config_path))
    raw_backend_port = config.get("port")
    backend_port_base = (
        _port(raw_backend_port, f"{config_path}.port") if isinstance(raw_backend_port, int) else DEFAULT_ENGINE_PORT
    )
    external_lb = config.get("data_parallel_external_lb", True)
    if not isinstance(external_lb, bool):
        raise ValueError(f"PD recipe {config_path}.data_parallel_external_lb must be a boolean")
    rpc_port_raw = config.get("data_parallel_rpc_port")
    rpc_port = _port(rpc_port_raw, f"{config_path}.data_parallel_rpc_port") if rpc_port_raw is not None else None
    transfer_path = f"{config_path}.kv_transfer_config"
    transfer = deepcopy(_required_mapping(config.get("kv_transfer_config"), transfer_path))
    connector_name = transfer.get("kv_connector")
    if not isinstance(connector_name, str) or not connector_name.strip():
        raise ValueError(f"PD recipe {transfer_path}.kv_connector must be a non-empty string")
    expected_kv_role = "kv_producer" if role is PdRole.PREFILL else "kv_consumer"
    if transfer.get("kv_role") != expected_kv_role:
        raise ValueError(
            f"PD recipe {transfer_path}.kv_role must be {expected_kv_role!r}; got {transfer.get('kv_role')!r}"
        )
    extra_path = f"{transfer_path}.kv_connector_extra_config"
    if connector_name == "MultiConnector":
        extra, kv_port = _normalize_multi_connector(transfer, transfer_path, expected_kv_role)
        extra_path += ".connectors[MooncakeConnectorV1].kv_connector_extra_config"
    else:
        extra = deepcopy(_required_mapping(transfer.get("kv_connector_extra_config"), extra_path))
        kv_port = _port(transfer.get("kv_port"), f"{transfer_path}.kv_port")
    engine_id_raw = transfer.get("engine_id")
    if engine_id_raw is None:
        engine_id = None
    elif isinstance(engine_id_raw, bool) or not isinstance(engine_id_raw, (int, str)):
        raise ValueError(f"PD recipe {transfer_path}.engine_id must be a non-negative integer or omitted")
    else:
        try:
            engine_id = int(engine_id_raw)
        except ValueError as exc:
            raise ValueError(
                f"PD recipe {transfer_path}.engine_id must be a non-negative integer; got {engine_id_raw!r}"
            ) from exc
        if engine_id < 0:
            raise ValueError(
                f"PD recipe {transfer_path}.engine_id must be a non-negative integer; got {engine_id_raw!r}"
            )

    prefill_raw = deepcopy(extra.get("prefill"))
    decode_raw = deepcopy(extra.get("decode"))
    prefill_shape = _parallel_shape(prefill_raw, f"{extra_path}.prefill")
    decode_shape = _parallel_shape(decode_raw, f"{extra_path}.decode")
    configured_tp = config.get("tensor_parallel_size")
    role_shape = prefill_shape if role is PdRole.PREFILL else decode_shape
    if configured_tp not in ("$7", role_shape.tp_size):
        raise ValueError(
            f"PD recipe {config_path}.tensor_parallel_size must be $7 or current role TP={role_shape.tp_size}; "
            f"got {configured_tp!r}"
        )

    for field in _RUNTIME_OWNED_ENGINE_FIELDS:
        config.pop(field, None)
    if connector_name != "MultiConnector":
        transfer.pop("kv_port", None)
        extra.pop("prefill", None)
        extra.pop("decode", None)
        if extra:
            transfer["kv_connector_extra_config"] = extra
        else:
            transfer.pop("kv_connector_extra_config", None)
    transfer.pop("engine_id", None)
    config["tensor_parallel_size"] = role_shape.tp_size
    config["kv_transfer_config"] = transfer

    env = deepcopy(_required_mapping(node.get("env", {}), f"{path}.env"))
    raw_system_setup = node.get("system_setup")
    source_commands = (
        extract_source_commands(
            raw_system_setup.get("commands", []),
            context=f"PD recipe {path}.system_setup",
        )
        if isinstance(raw_system_setup, dict)
        else []
    )
    return _NormalizedNode(
        role=role,
        index=index,
        source_prefix=path,
        engine_config=config,
        env=env,
        system_setup=deepcopy(raw_system_setup),
        source_commands=source_commands,
        prefill_shape=prefill_shape,
        decode_shape=decode_shape,
        connector_name=connector_name.strip(),
        rpc_port=rpc_port,
        backend_port_base=backend_port_base,
        data_parallel_external_lb=external_lb,
        kv_port=kv_port,
        engine_id=engine_id,
    )


def _normalize_nodes(strategy: Dict[str, Any], prefix: str) -> Dict[PdRole, list[_NormalizedNode]]:
    nodes = strategy.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError(f"PD recipe {prefix}.nodes must be a non-empty list")
    grouped: Dict[PdRole, list[_NormalizedNode]] = {PdRole.PREFILL: [], PdRole.DECODE: []}
    for position, raw in enumerate(nodes):
        role_name = raw.get("role") if isinstance(raw, dict) else None
        role = _ROLE_NAMES.get(role_name)
        expected_index = len(grouped[role]) if role is not None else 0
        node = _normalize_node(raw, f"{prefix}.nodes[{position}]", expected_index)
        grouped[node.role].append(node)
    for role, role_nodes in grouped.items():
        if not role_nodes:
            raise ValueError(f"PD recipe {prefix}.nodes is missing a node with role={role.value}")
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
            raise ValueError(f"PD recipe logical instance identity {identity!r} members must be contiguous")
        seen.add(identity)
        groups.append((identity, 1))
    member_counts = {count for _, count in groups}
    if len(member_counts) != 1:
        raise ValueError(
            f"PD recipe logical instances for one role must have equal Pod counts; got {sorted(member_counts)}"
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
                "PD recipe engine_id must increase consecutively from 0 in P-then-D logical-instance order; "
                f"got {engine_ids}"
            )
        engine_id_policy = PD_ENGINE_ID_FROM_INDEX
    else:
        raise ValueError("PD recipe P/D node engine_id values must be either all omitted or all explicit")

    ports = [kv_port for (_, kv_port) in identities]
    if len(set(ports)) != len(ports):
        raise ValueError(f"PD recipe kv_port must be unique across logical instances; got {ports}")
    strides = [right - left for left, right in zip(ports, ports[1:])]
    if not strides or strides[0] <= 0 or any(stride != strides[0] for stride in strides):
        raise ValueError(
            f"PD recipe kv_port must form a positive arithmetic sequence across logical instances; got {ports}"
        )
    return _IdentityProfile(engine_id_policy, ports[0], strides[0])


def _validate_role_nodes(nodes: list[_NormalizedNode], role: PdRole) -> _NormalizedNode:
    """确保一个 role 的所有节点仅 runtime-owned 字段不同。"""
    first = nodes[0]
    for node in nodes[1:]:
        if node.engine_config != first.engine_config:
            raise ValueError(
                f"PD recipe role={role.value} nodes have inconsistent static engine_config: {node.source_prefix}"
            )
        if node.env != first.env:
            raise ValueError(f"PD recipe role={role.value} nodes have inconsistent env: {node.source_prefix}")
        if node.source_commands != first.source_commands:
            raise ValueError(
                f"PD recipe role={role.value} nodes have inconsistent source commands: {node.source_prefix}"
            )
        if (node.prefill_shape, node.decode_shape) != (first.prefill_shape, first.decode_shape):
            raise ValueError(f"PD recipe role={role.value} nodes have inconsistent P/D shape: {node.source_prefix}")
        if node.connector_name != first.connector_name or node.rpc_port != first.rpc_port:
            raise ValueError(
                f"PD recipe role={role.value} nodes have inconsistent connector or DP RPC port: {node.source_prefix}"
            )
    return first


def select_pd_recipe_pair(
    model_data: Dict[str, Any], topology_input_policy: PdTopologyInputPolicy
) -> Dict[PdRole, PdRoleRecipe]:
    """从正式 ``pd_disaggregation.nodes[]`` recipe 生成内部 P/D role pair。

    外部 YAML 保留官方命令可直接表达的参数；rank、local DP、backend port、placement 和
    connector identity 在此被识别为 runtime-owned，后续由 planner 以 MaaS 输入派生。
    """
    if topology_input_policy not in _ALLOWED_INPUT_POLICIES:
        raise ValueError(f"Unknown PD topology input policy: {topology_input_policy!r}")
    strategy_name, prefix, strategy = _select_strategy(model_data)
    grouped = _normalize_nodes(strategy, prefix)
    first = {role: _validate_role_nodes(nodes, role) for role, nodes in grouped.items()}
    if (
        first[PdRole.PREFILL].prefill_shape != first[PdRole.DECODE].prefill_shape
        or first[PdRole.PREFILL].decode_shape != first[PdRole.DECODE].decode_shape
    ):
        raise ValueError("PD recipe P/D nodes must describe the same P/D parallel shape")
    identity = _derive_identity_profile(grouped)
    shape_policy = (
        PD_TOPOLOGY_DERIVED_1P1D
        if first[PdRole.PREFILL].prefill_shape.dp_size == 1 and first[PdRole.PREFILL].decode_shape.dp_size == 1
        else PD_TOPOLOGY_EXPLICIT_ALLOCATION
    )
    if topology_input_policy != shape_policy:
        raise ValueError(f"PD recipe accepts only {shape_policy!r}; got {topology_input_policy!r}")
    if shape_policy == PD_TOPOLOGY_EXPLICIT_ALLOCATION:
        missing_rpc_roles = [role.value for role, node in first.items() if node.rpc_port is None]
        if missing_rpc_roles:
            raise ValueError(
                f"PD explicit_allocation recipe is missing concrete DP RPC ports: roles={missing_rpc_roles}"
            )
    pair: Dict[PdRole, PdRoleRecipe] = {}
    runtime_profiles = _required_mapping(strategy.get("runtime", {}), f"{prefix}.runtime")
    for role, topology in ((PdRole.PREFILL, Topology.PD_PREFILL), (PdRole.DECODE, Topology.PD_DECODE)):
        node = first[role]
        role_name = "prefill" if role is PdRole.PREFILL else "decode"
        role_profile = _required_mapping(runtime_profiles.get(role_name, {}), f"{prefix}.runtime.{role_name}")
        if "engine_id_policy" in role_profile and any(item.engine_id is not None for item in grouped[role]):
            raise ValueError(
                f"PD recipe {prefix}.runtime.{role_name}.engine_id_policy cannot be combined with "
                f"nodes[{role_name}].engine_config.kv_transfer_config.engine_id"
            )
        engine_id_policy = role_profile.get("engine_id_policy", identity.engine_id_policy)
        if engine_id_policy not in {
            PD_ENGINE_ID_OMIT,
            PD_ENGINE_ID_FROM_INDEX,
        }:
            raise ValueError(f"PD recipe {prefix}.runtime.{role_name}.engine_id_policy is invalid")
        ordinary_1p1d = shape_policy == PD_TOPOLOGY_DERIVED_1P1D
        runtime = PdRuntimeSpec(
            topology_input_policy=shape_policy,
            prefill_shape=node.prefill_shape,
            decode_shape=node.decode_shape,
            # recipe 中 identity group 的成员数是已验收 topology 的参考值；实际 mPnD
            # 成员数由 MaaS placement 和显式 topology 决定，不在 planner 中作硬匹配。
            instance_member_count=_identity_groups(grouped[role])[0][1],
            process_layout=PD_PROCESS_LAYOUT_SINGLE if ordinary_1p1d else PD_PROCESS_LAYOUT_PER_LOCAL_RANK,
            dp_launch_policy=PD_DP_LAUNCH_NONE if ordinary_1p1d else PD_DP_LAUNCH_EXTERNAL_RANK,
            endpoint_policy=PD_ENDPOINT_PER_PROCESS,
            backend_port_base=node.backend_port_base,
            data_parallel_rpc_port=None if ordinary_1p1d else node.rpc_port,
            data_parallel_external_lb=node.data_parallel_external_lb,
            connector_profile=ConnectorProfile(
                connector_name=node.connector_name,
                engine_id_policy=engine_id_policy,
                kv_port_policy=KvPortPolicy(
                    mode=PD_KV_PORT_FROM_INDEX,
                    base=node.kv_port if node.connector_name == "MultiConnector" else identity.kv_base,
                    instance_stride=0 if node.connector_name == "MultiConnector" else identity.kv_stride,
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
            system_setup=node.system_setup,
            source_commands=node.source_commands,
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
