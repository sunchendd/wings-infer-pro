"""引擎首期交付边界与并行参数形态。

引擎特有的版本、拓扑和 native 参数差异集中在本模块。resolver/strategy 只查询
契约，不按引擎名分支。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ParallelismParamNames:
    """一个引擎用于表达 TP/DP/PP 的参数名及兼容别名。"""

    tp: str
    dp: str
    pp: str
    tp_aliases: tuple[str, ...] = ()
    dp_aliases: tuple[str, ...] = ()
    pp_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineDeliveryContract:
    """当前交付版本的引擎能力边界。"""

    parallelism: ParallelismParamNames
    required_version_prefix: str | None = None
    supported_topologies: frozenset[str] | None = None
    multi_node_member_count: int | None = None
    multi_node_max_dp: int | None = None
    multi_node_pp: int | None = None
    node_count_param: str | None = None
    node_rank_param: str | None = None
    rendezvous_address_param: str | None = None
    forbidden_true_params: frozenset[str] = frozenset()
    accel_policy: str = "allow"


_CANONICAL_PARALLELISM = ParallelismParamNames(
    tp="tensor_parallel_size",
    dp="data_parallel_size",
    pp="pipeline_parallel_size",
)

_SGLANG_PARALLELISM = ParallelismParamNames(
    tp="tp_size",
    dp="dp_size",
    pp="pp_size",
    tp_aliases=("tensor_parallel_size",),
    dp_aliases=("data_parallel_size",),
    pp_aliases=("pipeline_parallel_size",),
)

_DEFAULT_CONTRACT = EngineDeliveryContract(parallelism=_CANONICAL_PARALLELISM)

_ENGINE_CONTRACTS: dict[str, EngineDeliveryContract] = {
    "sglang": EngineDeliveryContract(
        parallelism=_SGLANG_PARALLELISM,
        required_version_prefix="v0.5.10",
        supported_topologies=frozenset({"standalone", "multi_node"}),
        multi_node_member_count=2,
        multi_node_max_dp=1,
        multi_node_pp=1,
        node_count_param="nnodes",
        node_rank_param="node_rank",
        rendezvous_address_param="dist_init_addr",
        forbidden_true_params=frozenset({"enable_dp_attention"}),
        accel_policy="drop_warn",
    ),
}


def get_engine_delivery_contract(engine: str) -> EngineDeliveryContract:
    """返回引擎交付契约；未声明引擎沿用既有通用行为。"""
    return _ENGINE_CONTRACTS.get(engine, _DEFAULT_CONTRACT)


def has_engine_delivery_contract(engine: str) -> bool:
    """返回引擎是否声明了额外交付边界。"""
    return engine in _ENGINE_CONTRACTS


def read_parallelism_values(
    engine_config: Mapping[str, Any],
    *,
    engine: str,
    default: int = 1,
) -> tuple[int, int, int]:
    """按引擎参数形态读取 TP/DP/PP；未提供的参数使用 default。"""
    names = get_engine_delivery_contract(engine).parallelism
    return (
        _read_parallelism_value(engine_config, names.tp, names.tp_aliases, default),
        _read_parallelism_value(engine_config, names.dp, names.dp_aliases, default),
        _read_parallelism_value(engine_config, names.pp, names.pp_aliases, default),
    )


def build_parallelism_override(
    *,
    engine: str,
    tp: int | None = None,
    dp: int | None = None,
    pp: int | None = None,
) -> dict[str, int]:
    """以引擎 native 参数名构造并行度覆盖层。"""
    names = get_engine_delivery_contract(engine).parallelism
    values = ((names.tp, tp), (names.dp, dp), (names.pp, pp))
    return {key: value for key, value in values if value is not None}


def validate_requested_version(engine: str, requested_version: str | None) -> None:
    """校验引擎受限版本请求，禁止受限引擎走 latest fallback。"""
    prefix = get_engine_delivery_contract(engine).required_version_prefix
    if prefix is None:
        return
    if requested_version is None or not _matches_version_prefix(requested_version, prefix):
        raise ValueError(
            f"engine={engine!r} supports only ENGINE_VERSION values beginning with {prefix!r} "
            f"and including the 'v' prefix; received {requested_version!r}."
        )


def validate_resolved_version(
    engine: str,
    requested_version: str | None,
    resolved_version: str,
) -> None:
    """校验受限版本的请求和最终目录均满足同一前缀。"""
    prefix = get_engine_delivery_contract(engine).required_version_prefix
    if prefix is None:
        return
    validate_requested_version(engine, requested_version)
    if not _matches_version_prefix(resolved_version, prefix):
        raise ValueError(
            f"engine={engine!r} supports only configuration directories beginning with {prefix!r}; "
            f"resolved {resolved_version!r}."
        )


def validate_topology(engine: str, topology: str) -> None:
    """校验引擎首期支持的 topology。"""
    supported = get_engine_delivery_contract(engine).supported_topologies
    if supported is not None and topology not in supported:
        raise ValueError(
            f"engine={engine!r} does not support topology={topology!r}; supported topologies are {sorted(supported)}."
        )


def validate_placement(
    engine: str,
    topology: str,
    node_ips: list[str] | None,
    *,
    rank_ip: str | None = None,
    master_ip: str | None = None,
) -> None:
    """校验受限多机拓扑的 placement；完全缺失时保留 dry-run 占位视图。"""
    contract = get_engine_delivery_contract(engine)
    if topology != "multi_node" or contract.multi_node_member_count is None:
        return
    if node_ips is None and rank_ip is None and master_ip is None:
        return
    if not node_ips or rank_ip is None or master_ip is None:
        raise ValueError(
            f"engine={engine!r} multi_node runtime placement requires NODE_IPS, RANK_IP and MASTER_IP together."
        )
    if len(node_ips) != contract.multi_node_member_count or len(set(node_ips)) != len(node_ips):
        raise ValueError(
            f"engine={engine!r} supports only {contract.multi_node_member_count} distinct Pods for multi_node; "
            f"received NODE_IPS={node_ips!r}."
        )
    if master_ip != node_ips[0]:
        raise ValueError(
            f"engine={engine!r} requires MASTER_IP to equal the first NODE_IPS entry; "
            f"received MASTER_IP={master_ip!r}, NODE_IPS={node_ips!r}."
        )
    if rank_ip not in node_ips:
        raise ValueError(
            f"engine={engine!r} requires RANK_IP to be present in NODE_IPS; "
            f"received RANK_IP={rank_ip!r}, NODE_IPS={node_ips!r}."
        )


def validate_recipe_node_count(engine: str, topology: str, node_count: int) -> None:
    """校验 multi_node recipe 展开的节点数。"""
    contract = get_engine_delivery_contract(engine)
    if topology != "multi_node" or contract.multi_node_member_count is None:
        return
    if node_count != contract.multi_node_member_count:
        raise ValueError(
            f"engine={engine!r} requires {contract.multi_node_member_count} recipe nodes for multi_node; "
            f"received {node_count}."
        )


def validate_final_parallelism(
    engine: str,
    topology: str,
    engine_config: Mapping[str, Any],
    *,
    expected_node_index: int | None = None,
    expected_tp: int | None = None,
    expected_rendezvous_address: str | None = None,
) -> None:
    """校验最终合并参数，防止高优先级层绕过首期边界。"""
    contract = get_engine_delivery_contract(engine)
    for key in contract.forbidden_true_params:
        if _is_true(engine_config.get(key)):
            raise ValueError(f"engine={engine!r} does not support {key}=true in this delivery scope.")

    _validate_parallelism_types(contract, engine_config)
    tp, dp, pp = read_parallelism_values(engine_config, engine=engine)
    if topology != "multi_node":
        return

    if contract.multi_node_max_dp is not None and dp > contract.multi_node_max_dp:
        raise ValueError(
            f"engine={engine!r} does not support multi_node DP>{contract.multi_node_max_dp}; "
            f"received {contract.parallelism.dp}={dp}."
        )
    if contract.multi_node_pp is not None and pp != contract.multi_node_pp:
        raise ValueError(
            f"engine={engine!r} supports only multi_node {contract.parallelism.pp}="
            f"{contract.multi_node_pp}; received {pp}."
        )
    if tp <= 0:
        raise ValueError(f"engine={engine!r} requires a positive integer {contract.parallelism.tp}.")
    if expected_tp is not None and tp != expected_tp:
        raise ValueError(
            f"engine={engine!r} requires multi_node {contract.parallelism.tp}={expected_tp} "
            f"to use the complete {contract.multi_node_member_count}-Pod world; received {tp}."
        )

    if expected_rendezvous_address is not None and contract.rendezvous_address_param is not None:
        actual = _required_value(engine_config, contract.rendezvous_address_param)
        if actual != expected_rendezvous_address:
            raise ValueError(
                f"engine={engine!r} requires runtime {contract.rendezvous_address_param}="
                f"{expected_rendezvous_address!r}; received {actual!r}."
            )

    _validate_node_identity(contract, engine_config, engine, expected_node_index)


def should_drop_accel(engine: str) -> bool:
    """当前引擎是否要求忽略 MaaS accel 开关。"""
    return get_engine_delivery_contract(engine).accel_policy == "drop_warn"


def _read_parallelism_value(
    engine_config: Mapping[str, Any],
    primary: str,
    aliases: tuple[str, ...],
    default: int,
) -> int:
    present = [key for key in (primary, *aliases) if key in engine_config]
    if not present:
        return default

    values = [(_as_positive_int(engine_config[key], key), key) for key in present]
    distinct_values = {value for value, _ in values}
    if len(distinct_values) > 1:
        details = ", ".join(f"{key}={value}" for value, key in values)
        raise ValueError(f"Conflicting parallelism parameter aliases: {details}.")
    return values[0][0]


def _validate_node_identity(
    contract: EngineDeliveryContract,
    engine_config: Mapping[str, Any],
    engine: str,
    expected_node_index: int | None,
) -> None:
    if contract.multi_node_member_count is None:
        return

    if contract.node_count_param is not None:
        node_count = _required_non_negative_int(engine_config, contract.node_count_param)
        if node_count != contract.multi_node_member_count:
            raise ValueError(
                f"engine={engine!r} requires multi_node {contract.node_count_param}="
                f"{contract.multi_node_member_count}; received {node_count}."
            )

    if contract.node_rank_param is None:
        return
    node_rank = _required_non_negative_int(engine_config, contract.node_rank_param)
    if node_rank >= contract.multi_node_member_count:
        raise ValueError(
            f"engine={engine!r} has {contract.node_rank_param}={node_rank} outside the "
            f"{contract.multi_node_member_count}-node range."
        )
    if expected_node_index is not None and node_rank != expected_node_index:
        raise ValueError(
            f"engine={engine!r} has {contract.node_rank_param}={node_rank}, which does not match "
            f"the current Pod index {expected_node_index}."
        )


def _required_non_negative_int(engine_config: Mapping[str, Any], key: str) -> int:
    if key not in engine_config:
        raise ValueError(f"multi_node final parameters are missing {key}.")
    value = getattr(engine_config[key], "final_value", engine_config[key])
    result = _strict_int(value, key, "non-negative")
    if result < 0:
        raise ValueError(f"{key} must be a non-negative integer; received {result}.")
    return result


def _validate_parallelism_types(
    contract: EngineDeliveryContract,
    engine_config: Mapping[str, Any],
) -> None:
    names = contract.parallelism
    for primary, aliases in (
        (names.tp, names.tp_aliases),
        (names.dp, names.dp_aliases),
        (names.pp, names.pp_aliases),
    ):
        for key in (primary, *aliases):
            if key in engine_config:
                _strict_positive_int(engine_config[key], key)


def _required_value(engine_config: Mapping[str, Any], key: str) -> Any:
    if key not in engine_config:
        raise ValueError(f"multi_node final parameters are missing {key}.")
    return getattr(engine_config[key], "final_value", engine_config[key])


def _as_positive_int(value: Any, key: str) -> int:
    value = getattr(value, "final_value", value)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a positive integer, not a boolean.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a positive integer; received {value!r}.") from exc
    if result <= 0:
        raise ValueError(f"{key} must be a positive integer; received {result}.")
    return result


def _strict_positive_int(value: Any, key: str) -> int:
    value = getattr(value, "final_value", value)
    result = _strict_int(value, key, "positive")
    if result <= 0:
        raise ValueError(f"{key} must be a positive integer; received {result}.")
    return result


def _strict_int(value: Any, key: str, requirement: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a {requirement} integer, not a boolean.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{key} must be a {requirement} integer; received {value!r}.") from exc
    raise ValueError(f"{key} must be a {requirement} integer; received {value!r}.")


def _matches_version_prefix(version: str, prefix: str) -> bool:
    if not version.startswith(prefix):
        return False
    suffix = version[len(prefix):]
    return not suffix or not suffix[0].isdigit()


def _is_true(value: Any) -> bool:
    value = getattr(value, "final_value", value)
    return value is True or (isinstance(value, str) and value.strip().casefold() in {"1", "true", "yes", "on"})
