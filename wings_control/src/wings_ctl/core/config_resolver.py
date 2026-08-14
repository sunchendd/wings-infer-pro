"""ConfigResolver — trace-aware 配置合并 + 场景选择。

职责:选 scenario/strategy → 按固定层序深合并出每个参数的 (值, trace) → 组装 ResolvedConfig。
不负责:读硬件/版本/yaml(上游 hardware/engines/loaders)、渲染 argv/脚本(下游 rendering/adapter)、
        真正算加速参数(委托 accel/smart_accel → wings_accel 包)。

输入:
  config_root (Path), hardware_family (str), engine (str),
  resolved_version (str), model_name (str), topology (Topology)

输出: ResolvedConfig

数据流: HardwareResolver → EngineResolver → ConfigResolver → (VllmAdapter)
不回调上游模块。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, NamedTuple

from wings_ctl import __version__ as WINGS_CTL_VERSION
from wings_ctl.accel.smart_accel import AccelResult, apply_smart_accel, collect_accel_switches
from wings_ctl.core.constants import DEFAULT_ENGINE_PORT
from wings_ctl.core.models import (
    ClusterPlacement,
    EngineProcessPlan,
    HardwareContext,
    ListenerPlan,
    PD_DP_LAUNCH_EXTERNAL_RANK,
    PD_DP_LAUNCH_NONE,
    PD_ENDPOINT_PER_PROCESS,
    PD_ENGINE_ID_FROM_INDEX,
    PD_ENGINE_ID_OMIT,
    PD_KV_LISTENER_DEVICE_COUNT_PLUS_ONE,
    PD_KV_LISTENER_SINGLE,
    PD_KV_PORT_FROM_INDEX,
    PD_LISTENER_OWNER_PER_PROCESS,
    PD_LISTENER_OWNER_PER_POD_CONNECTOR_GROUP,
    PD_PROCESS_LAYOUT_PER_LOCAL_RANK,
    PD_PROCESS_LAYOUT_SINGLE,
    PD_TOPOLOGY_DERIVED_1P1D,
    PD_TOPOLOGY_EXPLICIT_ALLOCATION,
    PdRole,
    PdRuntimeInput,
    PdRuntimeSpec,
    ProcessPlan,
    ResolvedConfig,
    ResolvedEnv,
    ResolvedPdTopology,
    ResolvedNode,
    SourceEvent,
    SystemSetup,
    Target,
    TracedValue,
    UserInput,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import _parse_version_tuple
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.loaders.locator import load_model_config, load_platform_config, resolve_family_dir
from wings_ctl.loaders.reasoning_table import ReasoningTableError, load_reasoning_table
from wings_ctl.pd.planner import resolve_pd_topology
from wings_ctl.pd.recipe import select_pd_recipe_pair
from wings_ctl.strategy.feature_inject import feature_inject_transform
from wings_ctl.strategy.feature_overlay import feature_overlay_transform
from wings_ctl.strategy.parallelism import check_capacity, dp_start_rank
from wings_ctl.strategy.post_template import post_template_strategy
from wings_ctl.strategy.reasoning_resolver import (
    build_model_identity,
    resolve_reasoning,
)
from wings_ctl.strategy.post_merge import apply_post_merge_strategy
from wings_ctl.strategy.topology_inject import (
    LAYOUT_TP_ACROSS,
    coordinate_parallelism,
    detect_layout,
    runtime_var_commands,
    select_node,
    substitute_literal_placeholders,
)
from wings_ctl.weight.reader import read_num_attention_heads, resolve_weight_bytes

logger = logging.getLogger(__name__)

# 内置最小默认值(最低优先级层):模板/用户都没给时由 wings-control 兜底。
# 引擎无关数据常量。模板有→覆盖;用户传→最高优先级覆盖。
# 注意：这里使用backend_port=17000，因为start_command.sh中的engine应该监听backend端口
# DEFAULT_ENGINE_PORT 单点定义在 core.constants(port_plan 复用同一常量,消除双写);
# 顶部已 import 并 re-export,保持既有 `from ...config_resolver import DEFAULT_ENGINE_PORT` 不变。
_BUILTIN_DEFAULTS: Dict[str, Any] = {"host": "0.0.0.0", "port": DEFAULT_ENGINE_PORT}


def _prepare_feature_context(
    config_root: Any,
    model_name: str,
    engine: str,
    model_data: Dict[str, Any] | None,
    reasoning_enabled: bool,
) -> tuple[Dict[str, Any], Any, str]:
    """按用户开关补全 reasoning feature，并保留其他模型特性。"""
    # 先复制整个 features，保留未来特性以及模型 YAML 中尚未迁移的配置。
    # 不直接修改 model_data，避免后续合并或审计读取到被 resolver 改写的数据。
    features = dict((model_data or {}).get("features") or {})
    reasoning_resolution = None
    reasoning_table_source = ""

    # reasoning parser 的唯一优先级顺序：
    #   0. 用户未显式开启 enable_auto_think_choice → 不处理、不加载公共表、不注入。
    #   1. 模型 YAML 的 features.reasoning.args → 最高优先级，直接使用，不再查公共表。
    #   2. reason_parser.yaml 的精确模型配置 → 仅在模型 YAML 未提供 override 时查询。
    #   3. 两处都没有精确配置 → 保持没有 reasoning feature，不开启 parser。
    if not reasoning_enabled:
        return features, reasoning_resolution, reasoning_table_source
    # 优先级 1：模型 YAML 显式 override。
    # 命中后直接返回，确保公共表不能覆盖模型 YAML 的显式配置，
    # 同时避免模型 YAML 已提供配置时依赖公共表文件。
    reasoning_feature = features.get("reasoning")
    if isinstance(reasoning_feature, dict) and reasoning_feature.get("args"):
        return features, None, reasoning_table_source

    try:
        # 优先级 2：模型 YAML 未配置时，查询 reason_parser.yaml 精确模型配置。
        loaded_reasoning = load_reasoning_table(config_root)
        reasoning_table_source = loaded_reasoning.source_path
        identity = build_model_identity(model_name, model_data)
        reasoning_resolution = resolve_reasoning(
            loaded_reasoning.data,
            identity,
            engine,
            table_source=reasoning_table_source,
        )
        if reasoning_resolution.status == "matched" and reasoning_resolution.spec:
            features["reasoning"] = {"args": list(reasoning_resolution.spec.args)}
        # 优先级 3：unmatched 时不写入 features.reasoning，即不开启 parser。
    except ReasoningTableError as exc:
        raise ValueError(f"reasoning parser table is invalid: {exc}") from exc
    # 返回补全后的特性集合，供 FeatureOverlay 处理。
    return features, reasoning_resolution, reasoning_table_source


def _evaluate_min_engine_version(
    model_data: Dict[str, Any] | None,
    engine_version_for_min_check: str | None,
) -> Dict[str, str]:
    """校验 model.min_engine_version 与参与校验的实际引擎版本。

    规则:
    - model 未命中或 min_engine_version 缺失: skip(不告警)
    - ENGINE_VERSION < min_engine_version: warn + WARNING
    - 其余: pass
    - 任意异常格式: skip + WARNING(不抛错)
    """
    check_value = engine_version_for_min_check or "unset"
    result: Dict[str, str] = {
        "min_engine_version": "unset",
        "engine_version_for_min_check": check_value,
        "min_engine_version_check": "skip",
        "min_engine_version_check_reason": "model_not_matched",
    }

    if not isinstance(model_data, dict):
        return result

    model_block = model_data.get("model", {})
    if not isinstance(model_block, dict):
        result["min_engine_version_check_reason"] = "model_block_missing"
        return result

    min_raw = model_block.get("min_engine_version")
    if min_raw is None or str(min_raw).strip() == "":
        result["min_engine_version_check_reason"] = "min_engine_version_unset"
        return result

    min_text = str(min_raw).strip()
    result["min_engine_version"] = min_text

    min_tuple = _parse_version_tuple(min_text)
    check_tuple = _parse_version_tuple(engine_version_for_min_check) if engine_version_for_min_check else None
    if min_tuple is None:
        result["min_engine_version_check_reason"] = "min_engine_version_invalid"
        logger.warning(
            "model.min_engine_version='%s' is invalid; skip min-engine check (warn-only)",
            min_text,
        )
        return result

    if check_tuple is None:
        if engine_version_for_min_check:
            result["min_engine_version_check_reason"] = "engine_version_for_min_check_invalid"
            logger.warning(
                "Engine version '%s' used for min-engine check is invalid; skip check (warn-only)",
                engine_version_for_min_check,
            )
        else:
            result["min_engine_version_check_reason"] = "engine_version_for_min_check_unset"
        return result

    if check_tuple < min_tuple:
        result["min_engine_version_check"] = "warn"
        result["min_engine_version_check_reason"] = "engine_version_below_min"
        logger.warning(
            "Engine version=%s used for min-check is lower than "
            "model.min_engine_version=%s; continue startup (warn-only)",
            engine_version_for_min_check,
            min_text,
        )
        return result

    result["min_engine_version_check"] = "pass"
    result["min_engine_version_check_reason"] = "engine_version_meets_min"
    return result


class NodeSpec(NamedTuple):
    """multi_node 归一后的单节点统一表示。

    任意形态(``nodes[]`` 或 ``head``·``worker``,**按数据结构判定、与引擎无关**)经 ``normalize_nodes``
    归一成 ``list[NodeSpec]``;后续选 node / 运行时协调 / 占位填充 / 渲染都只吃这个表示,**不再看引擎/形态**。

    Attributes:
        role: 节点角色(``head`` / ``worker`` / ascend 原标 ``node{i}``)。
        index: 节点在集群中的下标(0 = head);ascend 未标时为 None。
        engine_config: 该节点引擎参数模板(只读基线,后续按层合并)。
        env: 该节点 env 模板。
        system_setup: 该节点 system_setup 原始块(dict 或 None)。
        engine_config_source_prefix: engine_config 在 YAML 中的来源路径前缀。
        env_source_prefix: env 在 YAML 中的来源路径前缀。
        system_setup_source_prefix: system_setup 在 YAML 中的来源路径前缀。
        source_prefix: 该节点段的来源路径前缀(role/index 摘要溯源用)。
    """

    role: str
    index: int | None
    engine_config: Dict[str, Any]
    env: Dict[str, Any]
    system_setup: Any
    engine_config_source_prefix: str
    env_source_prefix: str
    system_setup_source_prefix: str
    source_prefix: str


def _make_node_spec(node: Any, *, role: str, index: int | None, node_prefix: str) -> NodeSpec:
    """把单节点 dict 归一为统一 ``NodeSpec``;role/index/source prefix 由调用方给。

    Args:
        node: 单节点原始 dict(含 engine_config/env/system_setup);非 dict 视为空。
        role: 节点角色。
        index: 节点下标(0 = head;None = 未标)。
        node_prefix: 该节点段在 yaml 中的来源路径前缀。

    Returns:
        归一后的 ``NodeSpec``。
    """
    node = node if isinstance(node, dict) else {}
    return NodeSpec(
        role=role,
        index=index,
        engine_config=node.get("engine_config", {}),
        env=node.get("env", {}),
        system_setup=node.get("system_setup"),
        engine_config_source_prefix=f"{node_prefix}.engine_config",
        env_source_prefix=f"{node_prefix}.env",
        system_setup_source_prefix=f"{node_prefix}.system_setup",
        source_prefix=node_prefix,
    )


def _from_nodes_list(nodes_raw: List[Any], strategy_prefix: str) -> List[NodeSpec]:
    """``nodes[]`` 形态 → ``NodeSpec`` 列表(逐项枚举映射)。"""
    specs: List[NodeSpec] = []
    for i, node in enumerate(nodes_raw):
        if isinstance(node, dict):
            role = node.get("role", f"node{i}")
            index = node.get("index")
        else:
            role = f"node{i}"
            index = None
        node_prefix = f"{strategy_prefix}.nodes[{i}]"
        specs.append(
            _make_node_spec(
                node,
                role=role,
                index=index,
                node_prefix=node_prefix,
            )
        )
    return specs


def _from_head_worker(strategy: Dict[str, Any], strategy_prefix: str, pod_count: int | None) -> List[NodeSpec]:
    """``head``/``worker`` 形态 → ``NodeSpec`` 列表(模板复用展开)。

    worker 是**单模板**,复用展开为 (pod_count-1) 个 worker;每个 worker 按 index 写 per-Pod 身份键,
    身份键按 ``detect_layout`` **单一判定**(TP 跨 Pod 写 ``node_rank=index``;
    DP 跨 Pod 写 ``data_parallel_start_rank=index×dp_local``)。
    pod_count 缺省取 head 的 ``nnodes``,再缺省 2。

    Args:
        strategy: 选定策略 dict(含 ``head`` / ``worker`` 段)。
        strategy_prefix: 策略在 yaml 中的来源路径前缀。
        pod_count: 集群 Pod 数(= len(NODE_IPS));None 时回退 head.nnodes → 2。

    Returns:
        ``[head, worker×(pod_count-1)]`` 的 ``NodeSpec`` 列表;head=index 0。
    """
    head = strategy.get("head") or {}
    worker = strategy.get("worker") or {}
    head_ec = head.get("engine_config", {}) or {}
    static_nnodes = head_ec.get("nnodes")
    if pod_count is None:
        # 无运行时上下文时,先用配方静态 nnodes,再缺省 2。
        pod_count = static_nnodes or 2
    elif static_nnodes is not None and static_nnodes != pod_count:
        # 运行时集群规模与配方静态 nnodes 不一致时 fail-fast。
        # multi_node 不自动改写 nnodes,否则可能出现 node_rank 越界的静默错配。
        raise ValueError(
            f"集群规模不一致:运行时 NODE_IPS 给出 {pod_count} 个 Pod,但 recipe nnodes={static_nnodes};"
            "multi_node 不自动改写 nnodes,请确认下发的 NODE_IPS 数量与配方一致。"
        )
    specs = [_make_node_spec(head, role="head", index=0, node_prefix=f"{strategy_prefix}.head")]
    for i in range(1, pod_count):
        ec = dict(worker.get("engine_config") or {})
        if detect_layout(ec) == LAYOUT_TP_ACROSS:  # TP 跨 Pod
            ec["node_rank"] = i
        elif "data_parallel_start_rank" in ec:  # DP 跨 Pod(start_rank 公式复用公共函数)
            ec["data_parallel_start_rank"] = dp_start_rank(i, ec.get("data_parallel_size_local") or 1)
        specs.append(
            _make_node_spec(
                {"engine_config": ec, "env": worker.get("env"), "system_setup": worker.get("system_setup")},
                role="worker",
                index=i,
                node_prefix=f"{strategy_prefix}.worker",
            )
        )
    return specs


def normalize_nodes(strategy: Dict[str, Any], strategy_prefix: str, pod_count: int | None) -> List[NodeSpec] | None:
    """multi_node 形态归一的**唯一入口**:任意形态 → ``list[NodeSpec]``。

    这里按 strategy 的数据形态集中分发,不把节点形态判断散落到调用方。新增
    recipe 写法时,在此增加一个形态分支和对应的 ``_from_xxx`` 归一函数,主干不改。

    Args:
        strategy: 选定策略 dict。
        strategy_prefix: 策略来源路径前缀。
        pod_count: 集群 Pod 数(head/worker 展开用)。

    Returns:
        ``list[NodeSpec]``(多机形态);若 strategy **既无 ``nodes[]`` 又无 ``head``/``worker``**,
        返回 ``None`` 表示"非多段形态"(交调用方按单段 engine_config 处理)。

    Raises:
        ValueError: 形态像多机(有 ``worker`` 却无 ``head`` 等)但无法归一时,列出 strategy 键 fail-fast。
    """
    nodes_raw = strategy.get("nodes")
    if isinstance(nodes_raw, list):  # nodes[] 形态:逐项枚举(ascend 及大量 nvidia recipe)
        specs = _from_nodes_list(nodes_raw, strategy_prefix)
        logger.info("multi_node 形态归一:nodes[] → %d 节点", len(specs))
        return specs
    if "head" in strategy or "worker" in strategy:  # head/worker 形态:复用展开(当前见于 nvidia)
        if "head" not in strategy:
            raise ValueError(f"multi_node 形态含 'worker' 但缺 'head',无法确定主节点:strategy 键={sorted(strategy)}")
        specs = _from_head_worker(strategy, strategy_prefix, pod_count)
        logger.info("multi_node 形态归一:head/worker → %d 节点", len(specs))
        return specs
    return None  # 非多段形态 → 交调用方按单段处理


def _select_scenario(
    model_data: Dict[str, Any],
    topology: Topology,
    pod_count: int | None = None,
) -> Dict[str, Any]:
    """从 model.yaml 选择 topology 对应场景,兼容多种形态(单段 / nodes[] / head·worker)。

    返回统一结构(单段:engine_config/env/system_setup + *_source_prefix;
    多机:额外 "nodes" = NodeSpec 列表)。

    兼容规则:
    - 旧格式: scenarios.{topology}.engine_config 直接存在 → 直接使用
    - strategies.{name} 按 default_strategy 三段式选定后,交 `normalize_nodes` 归一:
      · 含 `nodes[]`(ascend)/ `head`·`worker`(nvidia)→ `list[NodeSpec]`
      · 返回 None(非多段形态)→ 单段 engine_config
    - 节点形态只由 strategy 的数据结构决定;pod_count 供 head/worker 展开。
    """
    scenarios = model_data.get("scenarios", {})
    scenario_key = topology.value  # "standalone", "multi_node", etc.
    scenario = scenarios.get(scenario_key)
    if scenario is None:
        raise NotImplementedError(
            f"该 recipe 无 '{topology.value}' 场景(scenarios.{topology.value} 缺失);"
            f"本 recipe 可用场景: {list(scenarios.keys())}。"
            "请确认 --distributed/PD 等拓扑选择与所选模型 recipe 匹配。"
        )

    # 旧格式: direct engine_config/env/system_setup
    if isinstance(scenario, dict) and "engine_config" in scenario:
        return {
            "engine_config": scenario.get("engine_config", {}),
            "env": scenario.get("env", {}),
            "system_setup": scenario.get("system_setup"),
            "engine_config_source_prefix": f"scenarios.{scenario_key}.engine_config",
            "env_source_prefix": f"scenarios.{scenario_key}.env",
            "system_setup_source_prefix": f"scenarios.{scenario_key}.system_setup",
            "selected_strategy": None,
            "strategy_selection_source": "",
            "strategy_default_candidates": [],
        }

    # 新格式: scenarios.{topology}.strategies.{name}.*
    strategies = scenario.get("strategies") if isinstance(scenario, dict) else None
    if isinstance(strategies, dict) and len(strategies) > 0:
        default_strategy_names = [
            name
            for name, strategy in strategies.items()
            if isinstance(strategy, dict) and strategy.get("default_strategy") is True
        ]
        if len(default_strategy_names) == 1:
            strategy_name = default_strategy_names[0]
            selection_source = "default_strategy"
        elif len(default_strategy_names) == 0:
            strategy_name = next(iter(strategies.keys()))
            selection_source = "fallback_first_no_default"
            logger.warning(
                "scenarios.%s.strategies 无 default_strategy=true,按顺序取第一个策略 '%s'",
                scenario_key,
                strategy_name,
            )
        else:
            strategy_name = default_strategy_names[0]
            selection_source = "fallback_first_multiple_defaults"
            logger.warning(
                "scenarios.%s.strategies 存在多个 default_strategy=true (%s),按顺序取第一个 default '%s' (官网数据异常)",
                scenario_key,
                ",".join(default_strategy_names),
                strategy_name,
            )

        strategy = strategies[strategy_name]
        strategy_prefix = f"scenarios.{scenario_key}.strategies.{strategy_name}"

        # 多机形态归一:唯一入口 normalize_nodes,按 strategy 的数据结构判断 nodes[] 或 head/worker。
        # 返回 None = 非多段形态 → 落到下方单段 engine_config。
        node_specs = normalize_nodes(strategy, strategy_prefix, pod_count)
        if node_specs is not None:
            return {
                "nodes": node_specs,
                "engine_config": {},
                "env": {},
                "system_setup": None,
                "engine_config_source_prefix": f"{strategy_prefix}.nodes",
                "env_source_prefix": f"{strategy_prefix}.nodes",
                "system_setup_source_prefix": "",
                "selected_strategy": strategy_name,
                "strategy_selection_source": selection_source,
                "strategy_default_candidates": default_strategy_names,
            }

        return {
            "engine_config": strategy.get("engine_config", {}),
            "env": strategy.get("env", {}),
            "system_setup": strategy.get("system_setup"),
            "engine_config_source_prefix": f"{strategy_prefix}.engine_config",
            "env_source_prefix": f"{strategy_prefix}.env",
            "system_setup_source_prefix": f"{strategy_prefix}.system_setup",
            "selected_strategy": strategy_name,
            "strategy_selection_source": selection_source,
            "strategy_default_candidates": default_strategy_names,
        }

    # 回退:保持当前失败语义,显式报错结构缺失
    raise ValueError(
        f"Scenario '{scenario_key}' missing engine_config. "
        "Expected either direct 'engine_config' or nested 'strategies.{name}.engine_config'."
    )


def _peek_recipe_parallelism(
    model_data: Dict[str, Any] | None,
    topology: Topology,
    *,
    rank_ip: str | None = None,
    node_ips: List[str] | None = None,
    master_ip: str | None = None,
) -> tuple[int, int]:
    """轻量预读 recipe 的 TP/DP,供 accel KV 内存 auto 估算使用(不走 _select_scenario 的强校验)。

    覆盖所有 scenario 形态(对齐 ``_select_scenario`` / ``normalize_nodes`` 的形态识别):
    - 旧格式 ``scenarios.{topo}.engine_config``(直接平铺)→ 直接读
    - 新格式单段 ``strategies.{default}.engine_config`` → 选 default_strategy(无则取首个)后读
    - 新格式 ``nodes[]``(multi_node/ascend)→ 按 IP 选本 Pod node;无 IP → 取 head(index=0)
    - 新格式 ``head``/``worker``(multi_node/nvidia)→ 按 IP 判 head/worker 取对应;无 IP → 取 head

    本 Pod 角色判定(轻量复刻 ``select_node``,**不走强校验**):有 ``rank_ip+node_ips+master_ip``
    且 ``rank_ip in node_ips`` 时,``index = node_ips.index(rank_ip)``,head iff index==0;
    否则退化取 head(保守代表值,与 multi_node 占位加载语义一致)。

    recipe 缺失/scenario 缺失/字段缺失/类型异常 → ``(0, 0)``(accel 内部兜底 1×1)。
    不影响 fallback / 异常 recipe 路径(apply_smart_accel 自身有 try/except 兜底)。

    Args:
        model_data: recipe dict;None/非 dict → ``(0, 0)``。
        topology: 当前部署拓扑。
        rank_ip: 当前 Pod IP；与其余 placement 字段闭合时用于选择本 Pod node。
        node_ips: 有序集群成员 IP；缺失或与 ``rank_ip`` 不一致时退化为 head。
        master_ip: 集群 master IP；用于 head/worker 形态判定。

    Returns:
        ``(tp, dp)``:从命中的 engine_config 读 ``tensor_parallel_size``/``data_parallel_size``。
    """
    if not isinstance(model_data, dict) or not model_data:
        return 0, 0
    scenarios = model_data.get("scenarios")
    if not isinstance(scenarios, dict):
        return 0, 0
    scenario = scenarios.get(topology.value)
    if not isinstance(scenario, dict):
        return 0, 0

    # 1) 旧格式:scenarios.{topo}.engine_config 直接平铺
    ec = scenario.get("engine_config") if isinstance(scenario.get("engine_config"), dict) else None

    # 2) 新格式:scenarios.{topo}.strategies.{name}.*
    if ec is None:
        strategies = scenario.get("strategies")
        if isinstance(strategies, dict) and strategies:
            chosen = _pick_default_strategy(strategies)
            if isinstance(chosen, dict):
                ec = _pick_node_engine_config(
                    chosen,
                    rank_ip=rank_ip, node_ips=node_ips, master_ip=master_ip,
                )

    if not isinstance(ec, dict):
        return 0, 0

    def _to_int(v: Any) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    return _to_int(ec.get("tensor_parallel_size")), _to_int(ec.get("data_parallel_size"))


def _pick_default_strategy(strategies: Dict[str, Any]) -> Dict[str, Any] | None:
    """从 strategies 选默认策略(对齐 ``_select_scenario`` 选取规则,但**不打 warning 日志**)。

    - 取 ``default_strategy: true`` 的首个;无 → 取首个 dict 形态的 strategy。

    Args:
        strategies: ``{name: strategy_dict}`` 映射(非空)。

    Returns:
        选中的 strategy dict;无 dict 形态 → None。
    """
    for _name, strat in strategies.items():
        if isinstance(strat, dict) and strat.get("default_strategy") is True:
            return strat
    for _name, strat in strategies.items():
        if isinstance(strat, dict):
            return strat
    return None


def _pick_node_engine_config(
    strategy: Dict[str, Any],
    *,
    rank_ip: str | None,
    node_ips: List[str] | None,
    master_ip: str | None,
) -> Dict[str, Any] | None:
    """从 multi_node 形态 strategy 取本 Pod 的 engine_config(轻量,**不走 normalize_nodes/选 node 强校验**)。

    覆盖三种形态:
    - ``strategy.engine_config`` 直接平铺(单段 strategy)→ 直接返回
    - ``strategy.nodes[]`` → 按 IP 选 node;无 IP/不一致 → 取 index=0
    - ``strategy.head``/``worker`` → 按 IP 判 head/worker;无 IP → 取 head

    本 Pod 角色判定(复刻 ``select_node`` 的不变量,**失败时退化而非抛**):
    有 ``rank_ip+node_ips+master_ip`` 且 ``node_ips`` 非空且 ``rank_ip in node_ips`` 时:
        ``index = node_ips.index(rank_ip)``;``is_head = (index == 0) 或 (rank_ip == master_ip)``
    否则:退化为 head(取 index=0,保守代表值)。

    Args:
        strategy: 选定策略 dict(可能含 engine_config / nodes / head / worker)。
        rank_ip: 当前 Pod IP；与 ``node_ips`` 闭合时用于选择本 Pod node。
        node_ips: 有序集群成员 IP；缺失或不包含 ``rank_ip`` 时退化为 head。
        master_ip: 集群 master IP；用于 head/worker 形态判定。

    Returns:
        本 Pod node 的 engine_config dict;strategy 无任何形态 → None。
    """
    # 单段 strategy.engine_config 优先
    direct_ec = strategy.get("engine_config")
    if isinstance(direct_ec, dict):
        return direct_ec

    # nodes[] 形态:按 IP 选 index,无 IP 取 0
    nodes_raw = strategy.get("nodes")
    if isinstance(nodes_raw, list) and nodes_raw:
        index = _resolve_pod_index(
            rank_ip=rank_ip, node_ips=node_ips, master_ip=master_ip,
            fallback=len(nodes_raw),  # 越界时退化取 0(下方 clamp)
        )
        if index is None or index >= len(nodes_raw):
            index = 0
        node = nodes_raw[index]
        ec = node.get("engine_config") if isinstance(node, dict) else None
        return ec if isinstance(ec, dict) else None

    # head/worker 形态:按 IP 判 head/worker,无 IP 取 head
    if "head" in strategy or "worker" in strategy:
        is_head = _resolve_is_head(
            rank_ip=rank_ip, node_ips=node_ips, master_ip=master_ip,
        )
        role_block = strategy.get("head") if is_head else strategy.get("worker")
        ec = role_block.get("engine_config") if isinstance(role_block, dict) else None
        return ec if isinstance(ec, dict) else None

    return None


def _resolve_pod_index(
    *,
    rank_ip: str | None,
    node_ips: List[str] | None,
    master_ip: str | None,
    fallback: int = 0,
) -> int | None:
    """轻量按 IP 解析本 Pod 在集群中的下标(复刻 ``select_node`` 不变量,**失败返回 None 而非抛**)。

    成功条件(任一不满足 → None,调用方退化取 head):
    - ``rank_ip`` 非空
    - ``node_ips`` 非空 list
    - ``rank_ip in node_ips``

    成功 → ``node_ips.index(rank_ip)``(head=0)。

    Args:
        rank_ip: 本 Pod IP。
        node_ips: 全集群 IP 列表(按序,首位须为 master)。
        master_ip: master IP(当前判定里仅作冗余校验,index=0 即 head,与 master 等价)。
        fallback: 不传(默认 0);保留参数以兼容未来"无 IP 但已知 index"场景。

    Returns:
        本 Pod 下标;无法判定 → None。
    """
    if not rank_ip or not node_ips or rank_ip not in node_ips:
        return None
    return node_ips.index(rank_ip)


def _resolve_is_head(
    *,
    rank_ip: str | None,
    node_ips: List[str] | None,
    master_ip: str | None,
) -> bool:
    """轻量判定本 Pod 是否为 head(复刻 ``select_node`` 不变量,**失败时保守返回 True 取 head 配置**)。

    判定:``rank_ip in node_ips`` 且 ``node_ips[0] == rank_ip``(与 master 等价,index 0 即 head)。
    无 IP 上下文/不一致 → True(退化取 head,与 multi_node 占位加载语义一致)。
    """
    if not rank_ip or not node_ips or rank_ip not in node_ips:
        return True  # 退化:取 head
    return node_ips.index(rank_ip) == 0


def _deep_merge(base: dict, override: dict) -> dict:
    """递归深合并两个 dict:同为 dict 的键递归合并,其余 override 整体覆盖。

    多机/PD 的嵌套结构(kv_transfer_config / compilation_config / additional_config 等)
    可能跨层出现,需逐层递归合并内层键,而非第二层整块替换。

    规则:
    - 两边都是 dict → 递归合并;
    - 其余(标量 / list / 类型不一致)→ override 整体覆盖(list 不逐元素合并,守 E3)。

    Args:
        base: 低优先层的 dict 值。
        override: 高优先层的 dict 值(冲突时胜出)。

    Returns:
        合并后的**新** dict(不修改入参)。
    """
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _build_system_setup(
    raw: Any,
    source_file: str,
    source_path: str,
    *,
    commands_override: List[str] | None = None,
) -> SystemSetup | None:
    """从场景层 ``system_setup`` 原始 dict 构建 ``SystemSetup``。

    Args:
        raw: yaml 里的 system_setup 块(dict 或 None)。
        source_file: 来源文件路径(用于 audit)。
        source_path: 该块在 yaml 中的路径前缀。
        commands_override: 若给定,用它替换 commands(用于运行时注入场景)。

    Returns:
        SystemSetup 实例;``raw`` 非 dict(含 None)且无 commands_override 时返回 None。
    """
    if not isinstance(raw, dict):
        if commands_override:
            return SystemSetup(commands=list(commands_override), source_file=source_file, source_path=source_path)
        return None
    return SystemSetup(
        sysctls=raw.get("sysctls", {}),
        sysfs_writes=raw.get("sysfs_writes", []),
        commands=commands_override if commands_override is not None else raw.get("commands", []),
        source_file=source_file,
        source_path=source_path,
    )


class MergeLayer(NamedTuple):
    """trace_merge 的一个合并层:把旧版四条平行列表的同一下标打包成具名结构。

    加一个合并层 = 往 trace_merge 的 list 里加一个 MergeLayer,列表顺序即层序(低→高优先);
    再不用在四条平行 list 的同一位置手动对齐(那是旧写法最易出错的地方)。

    Attributes:
        name: 层名,写进 TracedValue.final_layer 与 events[].layer(如 ``"user_cli"``)。
        data: 该层参数 dict(key→value)。
        source_file: 该层来源文件路径(trace 溯源;如 ``"<user_cli>"`` 或真实 yaml 路径)。
        source_path_prefix: 该层来源路径前缀(拼 source_path 用;空串 = 无前缀)。
        source_overrides: 可选的逐参数 ``(source_file, source_path)``，用于同一合并层内
            参数来自不同配置位置的场景。
    """

    name: str
    data: Dict[str, Any]
    source_file: str
    source_path_prefix: str
    source_overrides: Dict[str, tuple[str, str]] | None = None


def trace_merge(layers: List[MergeLayer]) -> Dict[str, TracedValue]:
    """Trace-aware 多层合并。

    低优先级在前,高优先级在后。后层覆盖前层。
    对每个 key 记录完整 events 链。

    规则:
    - dict 值**递归深合并**(_deep_merge:同为 dict 的内层键递归合并)
    - list 值整体替换(E3)
    - 标量值直接覆盖

    每个 ``MergeLayer`` 自带 (name / data / source_file / source_path_prefix);**加一层 =
    往 layers 里加一个 MergeLayer**,列表顺序即层序(低→高优先)。旧版用四条平行 list、靠同
    下标对齐,漏一列就串层/丢层;结构化后这类"下标错位"从源头消失。

    Returns:
        Dict[str, TracedValue] — 每个 key 对应完整追踪。
    """
    merged: Dict[str, TracedValue] = {}

    for layer in layers:
        layer_name, src_file, path_prefix = layer.name, layer.source_file, layer.source_path_prefix
        for key, value in layer.data.items():
            override_source = (layer.source_overrides or {}).get(key)
            event_file, event_path = override_source or (src_file, f"{path_prefix}.{key}" if path_prefix else key)
            source_path = event_path
            event = SourceEvent(
                action="set" if key not in merged else "override",
                layer=layer_name,
                value=value,
                source_file=event_file,
                source_path=source_path,
            )

            if key in merged:
                existing = merged[key]
                # dict 值递归深合并:嵌套内层键逐层合并,不再第二层整块替换
                if isinstance(existing.final_value, dict) and isinstance(value, dict):
                    deep_merged = _deep_merge(existing.final_value, value)
                    merged[key] = TracedValue(
                        final_value=deep_merged,
                        final_layer=layer_name,
                        source_file=event_file,
                        source_path=source_path,
                        events=existing.events + [event],
                    )
                else:
                    # 标量/list: 整体替换
                    merged[key] = TracedValue(
                        final_value=value,
                        final_layer=layer_name,
                        source_file=event_file,
                        source_path=source_path,
                        events=existing.events + [event],
                    )
            else:
                merged[key] = TracedValue(
                    final_value=value,
                    final_layer=layer_name,
                    source_file=event_file,
                    source_path=source_path,
                    events=[event],
                )

    return merged


def _resolve_multi_node(
    node_specs: List[NodeSpec],
    *,
    model_path: Any,
    user_layer: dict,
    feature_overrides: dict,
    feature_trace_sources: dict[str, tuple[str, str]],
    accel_overrides: dict,
    device_count: int | None,
    rank_ip: str | None,
    node_ips: List[str] | None,
    master_ip: str | None,
    hardware: HardwareContext | None = None,
    weights_path: Any = None,
    strategy_env_layer: dict | None = None,
    strategy_feature_inject_overrides: dict | None = None,
) -> tuple[
    Dict[str, TracedValue],
    Dict[str, TracedValue],
    SystemSetup | None,
    List[ResolvedNode] | None,
    dict,
]:
    """multi_node 解析:逐节点深合并;有运行时上下文则选本 Pod 节点升顶层注入,否则占位。

    每节点 engine_config 走 ``trace_merge``(builtin_default → model_scenario [→ strategy_multinode_dp]
    → user_cli),嵌套结构深合并。无运行时上下文时 ``$占位符`` 按字面保留;
    运行时上下文齐全时,由 ``system_setup.commands`` 在 shell 中填充(见 ``strategy.topology_inject``)。

    Args:
        node_specs: ``_select_scenario`` 产出的 per-node spec 列表(含各自 source prefix)。
        model_path: 命中的 model.yaml 路径(trace 溯源)。
        user_layer: user_cli 覆盖层(对每个节点统一应用)。
        feature_overrides: FeatureOverlay 产出的特性覆盖层(模型级,对每个节点统一应用;空=无特性)。
        feature_trace_sources: FeatureOverlay 每个参数的真实来源文件和路径。
        accel_overrides: wings-accel 产出的 engine_config 合并层(模型级,对每个节点统一应用;
            排 strategy_feature 后、user_cli 前 → recipe < accel < user_cli;空=无加速产出)。
        device_count: 本 Pod 卡数(None 不触发多机 DP 协调)。
        rank_ip: 当前 Pod IP；与 ``node_ips`` 同时存在时进入运行时注入路径。
        node_ips: 有序集群成员 IP；用于选择当前 Pod 对应的 node recipe。
        master_ip: 集群 master IP；用于 head 判定和 DP 协调地址注入。
        hardware: TP 跨机收缩显存闸使用的硬件上下文；其它路径可为 ``None``。
        weights_path: TP 跨机收缩显存闸读取模型权重信息的路径。
        strategy_env_layer: 特性注入层（SmartQoS/EnableTrace/Metrics）产出的环境变量覆盖层，
            由调用方在 resolve_config 中统一计算后传入。
        strategy_feature_inject_overrides: 特性注入层产出的引擎参数覆盖层，
            由调用方在 resolve_config 中统一计算后传入。

    Returns:
        ``(engine_config_traces, env_traces, system_setup, nodes, notes)``:
        - 注入路径:选中节点升顶层(含 DP 协调 + 占位填充),``nodes=None``。
        - 占位路径:顶层留空,``nodes`` = 全集群占位视图,``system_setup=None``。

    Raises:
        ValueError: 选 node 强校验失败 / DP 协调越界(透传自 strategy.topology_inject)。
    """
    model_path_str = str(model_path)
    pod_count = len(node_specs)

    # extra_layers 直接用 MergeLayer 表达 multi_node 注入层(名/数据/来源文件/来源路径前缀),
    # 避免位置字段顺序不清;这些层插在 model_scenario 后、user_cli 前。加一个多机 merge layer = 追加一个 MergeLayer。
    def _ec_traces(spec: NodeSpec, *, extra_layers: List[MergeLayer] = ()) -> Dict[str, TracedValue]:
        """单节点 engine_config 的 trace_merge;extra_layers 在 model_scenario 后、user_cli 前插入。"""
        merge_layers: List[MergeLayer] = [
            MergeLayer("builtin_default", _BUILTIN_DEFAULTS, "<builtin_default>", "builtin_default"),
            MergeLayer("model_scenario", spec.engine_config, model_path_str, spec.engine_config_source_prefix),
        ]
        for layer in extra_layers:
            if layer.data:  # 数据为空的层不成层(no-op),与旧逻辑一致
                merge_layers.append(layer)
        merge_layers.append(MergeLayer("user_cli", user_layer, "<user_cli>", "user_cli"))
        return trace_merge(merge_layers)

    def _env_traces(spec: NodeSpec, *, override: dict | None = None) -> Dict[str, TracedValue]:
        merge_layers: List[MergeLayer] = [
            MergeLayer("model_scenario", spec.env, model_path_str, spec.env_source_prefix),
        ]
        if override:
            merge_layers.append(
                MergeLayer(
                    "strategy_topology_inject",
                    override,
                    "<strategy:topology_inject>",
                    "strategy.topology_inject",
                )
            )
        if strategy_env_layer:
            merge_layers.append(
                MergeLayer(
                    "strategy_feature_env",
                    strategy_env_layer,
                    "<strategy:feature_env_inject>",
                    "strategy.feature_env_inject",
                ),
            )
        return trace_merge(merge_layers)

    if rank_ip is not None and node_ips is not None:
        # 注入路径:选本 Pod 节点 + DP 调整 + 占位注入,升顶层可执行。
        sel = select_node(pod_count, rank_ip=rank_ip, node_ips=node_ips, master_ip=master_ip)
        spec = node_specs[sel.index]
        if device_count is not None and detect_layout(spec.engine_config) == LAYOUT_TP_ACROSS:
            if hardware is None:
                raise ValueError("TP 跨机收缩需要硬件上下文以执行显存校验")
            _preflight_shrink_gate(
                spec.engine_config,
                pod_count * device_count,
                hardware,
                weights_path,
            )
        dp_override, dp_notes = coordinate_parallelism(
            spec.engine_config,
            device_count=device_count,
            pod_count=pod_count,
            index=sel.index,
        )
        # 字面占位替换($local_ip/$node0_ip → 真实 IP),单独记一层 trace。
        # argv 里需要是字面值;$nic_name 这类运行时变量保留给 shell 展开。
        ec_inject = substitute_literal_placeholders(spec.engine_config, rank_ip=rank_ip, master_ip=master_ip)
        env_inject = substitute_literal_placeholders(spec.env, rank_ip=rank_ip, master_ip=master_ip)
        ec_traces = _ec_traces(
            spec,
            extra_layers=[
                MergeLayer("strategy_multinode_dp", dp_override, "<strategy:multinode_dp>", "strategy.multinode_dp"),
                MergeLayer(
                    "strategy_topology_inject", ec_inject, "<strategy:topology_inject>", "strategy.topology_inject"
                ),
                MergeLayer(
                    "strategy_feature",
                    feature_overrides,
                    "<strategy:feature>",
                    "strategy.feature",
                    feature_trace_sources,
                ),
                MergeLayer(
                    "strategy_feature_inject",
                    strategy_feature_inject_overrides or {},
                    "<strategy:feature_inject>",
                    "strategy.feature_inject",
                ),
                MergeLayer("strategy_accel", accel_overrides, "<wings-accel>", "strategy.accel"),
            ],
        )
        env_traces = _env_traces(spec, override=env_inject)

        # system_setup:commands 仅保留运行时 nic 探测(若被 env 引用);特权 sysctls/sysfs 原样(渲染层注释)。
        raw_ss = spec.system_setup
        nic_cmds = runtime_var_commands(spec.engine_config, spec.env)
        system_setup = _build_system_setup(
            raw_ss,
            model_path_str,
            spec.system_setup_source_prefix,
            commands_override=nic_cmds,
        )

        notes = {
            "multi_node_role": sel.role,
            "multi_node_index": str(sel.index),
            "multi_node_pod_count": str(pod_count),
            "multi_node_node_ips": ",".join(node_ips),
            "multi_node_injection_status": "injected",
        }
        notes.update(dp_notes)
        logger.info("multi_node 注入完成:role=%s index=%d pod_count=%d", sel.role, sel.index, pod_count)
        return ec_traces, env_traces, system_setup, None, notes

    # 占位路径:无运行时上下文时产全集群占位视图,不注入。
    resolved_nodes: List[ResolvedNode] = []
    for spec in node_specs:
        extra_layers = [
            MergeLayer(
                "strategy_feature",
                feature_overrides,
                "<strategy:feature>",
                "strategy.feature",
                feature_trace_sources,
            ),
            MergeLayer(
                "strategy_feature_inject",
                strategy_feature_inject_overrides or {},
                "<strategy:feature_inject>",
                "strategy.feature_inject",
            ),
            MergeLayer("strategy_accel", accel_overrides, "<wings-accel>", "strategy.accel"),
        ]
        engine_config_traces = _ec_traces(spec, extra_layers=extra_layers)
        env_traces = _env_traces(spec)
        system_setup = _build_system_setup(
            spec.system_setup,
            model_path_str,
            spec.system_setup_source_prefix,
        )
        resolved_nodes.append(
            ResolvedNode(
                role=spec.role,
                index=spec.index,
                engine_config_traces=engine_config_traces,
                env_traces=env_traces,
                system_setup=system_setup,
                source_prefix=spec.source_prefix,
            )
        )
    notes = {
        "multi_node_node_count": str(len(resolved_nodes)),
        "multi_node_roles": ",".join(n.role for n in resolved_nodes),
        "multi_node_injection_status": "pending_runtime_context",
    }
    logger.info(
        "multi_node 占位加载(无运行时上下文):nodes=%d roles=%s",
        len(resolved_nodes),
        notes["multi_node_roles"],
    )
    return {}, {}, None, resolved_nodes, notes


def _preflight_shrink_gate(
    scenario_engine_config: Dict[str, Any],
    device_count: int | None,
    hardware: HardwareContext,
    weights_path: Any,
) -> None:
    """TP 收缩的前置校验:仅当 ``cnt < 模板 TP`` 时触发。

    在并行策略实际收缩 TP 之前运行，防止把装不下的模型缩小 TP 后直接启动:
    通过**显存硬闸**(``cnt × gpu_mem ≥ 1.5 × weight_bytes``,裸 gpu_mem 无 util)
    和 **heads 守卫**(``num_attention_heads % cnt == 0``,config 读不到则 warn-skip)。
    ``cnt ≥ TP``(不收缩)直接返回，不读取 gpu_mem/权重；``cnt`` 可以是单机卡数，
    也可以是 TP 跨 Pod 场景的全局 ``world_size``。

    Args:
        scenario_engine_config: 选定模板 engine_config(读 ``tensor_parallel_size``)。
        device_count: 实际参与 TP 的卡数；单机为本机卡数，多机 TP-across 为全局卡数
            (``pod_count × 每 Pod 卡数``)，None 表示不触发。
        hardware: 硬件上下文(读 ``gpu_mem_gb``,来自 hardware_family 的 _<N>G 后缀)。
        weights_path: 模型权重目录(``--model-path``;读 weight_bytes / num_attention_heads)。

    Raises:
        ValueError: 无显存后缀 / 无权重路径 / 权重不可读 / 容量不足 / heads 不整除。
    """
    if device_count is None:
        return
    tp = scenario_engine_config.get("tensor_parallel_size", 1)
    if device_count >= tp:
        return  # 不收缩时不触发前置闸
    # 单卡显存唯一来自 hardware_family 的 _<N>G 后缀(resolve_hardware 已解析进 gpu_mem_gb)。
    gpu_mem_gb = hardware.gpu_mem_gb
    if gpu_mem_gb is None:
        raise ValueError(
            "TP 收缩(device-count<TP)需前置显存闸,但 hardware_family 无 _<N>G 显存后缀、"
            "拿不到单卡显存(gpu_mem);请在 hardware_family 带上单卡显存,如 h20_96G。"
        )
    if not weights_path:
        raise ValueError("无 --model-path:TP 收缩需读权重体积过显存闸。")
    gpu_mem_bytes = int(gpu_mem_gb) * 2**30
    weight_bytes = resolve_weight_bytes(str(weights_path))
    check_capacity(device_count, gpu_mem_bytes, weight_bytes)  # tp_eff=cnt(收缩后)
    heads = read_num_attention_heads(str(weights_path))
    if heads is not None and heads % device_count != 0:
        raise ValueError(
            f"num_attention_heads={heads} 不被 device-count={device_count} 整除:"
            f"TP 收缩到 {device_count} 无法切分(收缩守卫);请调整卡数或用 direct_vllm_serve。"
        )
    logger.info(
        "TP 收缩前置闸通过:cnt=%d gpu_mem=%dG weight_bytes=%d",
        device_count,
        int(gpu_mem_gb),
        weight_bytes,
    )


def _build_user_cli_audit_entries(
    user_layer: Dict[str, Any],
    user_cli_dropped: List[Dict[str, Any]] | None,
) -> List[Dict[str, Any]]:
    """把 user_cli 覆盖层 + 被丢弃项汇成 audit 展示条目(applied / dropped)。

    Args:
        user_layer: 已应用的 user_cli 覆盖 dict(key→value)。
        user_cli_dropped: 被契约过滤/翻译丢弃的项列表(含 key/value/reason)。

    Returns:
        条目列表:applied 项 ``status="applied"``;dropped 项带 ``status="dropped"`` + reason。
    """
    entries: List[Dict[str, Any]] = [{"key": k, "value": v, "status": "applied"} for k, v in user_layer.items()]
    for item in user_cli_dropped or []:
        entries.append(
            {
                "key": item.get("key"),
                "value": item.get("value"),
                "status": "dropped",
                "reason": item.get("reason", "maas_status=丢弃"),
            }
        )
    return entries


def _merge_engine_config_traces(
    scenario_engine_config: dict,
    strategy_overrides: dict,
    feature_overrides: dict,
    feature_trace_sources: dict[str, tuple[str, str]],
    accel_layer: dict,
    user_layer: dict,
    *,
    model_layer_name: str,
    model_source_file: str,
    scenario_prefix: str,
    feature_inject_overrides: dict | None = None,
) -> Dict[str, TracedValue]:
    """按固定层序深合并出 engine_config 逐参 trace(standalone 命中 / fallback 兜底共用)。

    层序(低→高优先级,trace-first):builtin_default < model(recipe) <
    strategy_device_count < strategy_feature < strategy_feature_inject <
    strategy_accel < user_cli。accel 层排 feature 后、user_cli 前 → recipe < accel < user_cli。

    Args:
        scenario_engine_config: recipe/平台基线的 engine_config(model 层)。
        strategy_overrides: 小策略层 device_count 覆盖层。
        feature_overrides: FeatureOverlay 覆盖层。
        feature_trace_sources: FeatureOverlay 每个参数的真实来源文件和路径。
        accel_layer: wings-accel 结构化 engine_config(空 dict = 无产出,合并 no-op)。
        user_layer: user_cli 最高优先覆盖层。
        model_layer_name: model 层名——standalone 命中为 ``"model_scenario"``,
            fallback 兜底为 ``"default_model"``。
        model_source_file: model 层来源文件路径(供 trace 溯源)。
        scenario_prefix: model 层 yaml 路径前缀。
        feature_inject_overrides: SmartQoS/EnableTrace/Metrics 特性注入覆盖层。

    Returns:
        参数名 → TracedValue。
    """
    # 每个 MergeLayer = 一个合并层;列表顺序即层序(低→高优先):
    #   builtin_default < model(recipe) < strategy_device_count < strategy_feature < strategy_accel < user_cli。
    # 加一个 merge layer = 往这个 list 里插一个 MergeLayer(名 / 数据 / 来源文件 / 来源路径前缀)。
    feature_source_file = "<strategy:feature>"
    feature_source_prefix = "strategy.feature"
    layers: list[MergeLayer] = [
        MergeLayer("builtin_default", _BUILTIN_DEFAULTS, "<builtin_default>", "builtin_default"),
        MergeLayer(model_layer_name, scenario_engine_config, model_source_file, scenario_prefix),
        MergeLayer("strategy_device_count", strategy_overrides, "<strategy:device_count>", "strategy.device_count"),
        MergeLayer(
            "strategy_feature", feature_overrides, feature_source_file, feature_source_prefix,
            feature_trace_sources,
        ),
    ]
    if feature_inject_overrides:
        layers.append(
            MergeLayer(
                "strategy_feature_inject",
                feature_inject_overrides,
                "<strategy:feature_inject>",
                "strategy.feature_inject",
            ),
        )
    layers.extend(
        [
            MergeLayer("strategy_accel", accel_layer, "<wings-accel>", "strategy.accel"),
            MergeLayer("user_cli", user_layer, "<user_cli>", "user_cli"),
        ]
    )
    return trace_merge(layers)


def _resolve_platform_fallback(
    *,
    platform_data: Dict[str, Any],
    platform_path: Any,
    platform_env: dict,
    topology: Topology,
    model_name: str,
    user_layer: dict,
    feature_overrides: dict,
    feature_trace_sources: dict[str, tuple[str, str]],
    accel_layer: dict,
    strategy_env_layer: dict | None,
    strategy_feature_inject_overrides: dict | None,
    device_count: int | None,
    hardware: HardwareContext,
    weights_path: Any,
    rank_ip: str | None,
    node_ips: List[str] | None,
    master_ip: str | None,
) -> tuple[
    Dict[str, TracedValue],
    Dict[str, TracedValue],
    SystemSetup | None,
    List[ResolvedNode] | None,
    dict,
    str,
]:
    """用平台 default_model 配置兜底解析未命中的模型。

    模型 recipe 未命中时，根据请求的 topology 从 ``default_model.yaml``
    选择平台默认场景并生成可渲染的配置。多机场景保留每个节点的
    ``head``/``worker`` 或 ``nodes`` 配置，并通过 ``_resolve_multi_node``
    生成节点级命令；单段场景则生成普通引擎配置。

    处理规则:
        1. 选择与 ``topology`` 对应的平台场景。
        2. 为没有模型配置的场景补充请求中的模型名。
        3. 多机场景按节点模板解析，保留节点角色和并行参数。
        4. 合并策略、特性、智能加速和用户参数，并记录来源链。
        5. 用户显式的 ``model`` / ``model_path`` 始终优先于 fallback 模型名。

    Returns:
        ``(engine_config_traces, env_traces, system_setup, nodes, notes, pattern)``。
        ``nodes`` 在无运行时上下文时保存全集群占位节点；有运行时上下文时为 None。
    """
    # default_model.yaml 可能缺失；这里保留一个可写入 trace 的占位路径，
    # 让 fallback 的审计信息仍能说明配置来源。
    platform_path_str = str(platform_path) if platform_path is not None else "<absent>"

    # topology 已由 CLI 大策略层确定；这里只按该 topology 选择平台场景，
    # 不再重新判断 standalone / multi_node / PD。
    platform_scenario = _select_scenario(platform_data, topology)
    platform_node_specs = platform_scenario.get("nodes")
    fallback_pattern = "<fallback_default_model>"

    if platform_node_specs:
        # 多机场景被 _select_scenario 统一成 NodeSpec 列表。逐节点保留配置，
        # 确保 head/worker 的角色、node_rank、nnodes 等参数完整传递。
        fallback_node_specs = []
        for spec in platform_node_specs:
            # 复制配置而不是原地修改 platform_data，避免污染 YAML 加载结果，
            # 也避免同一个配置对象在后续解析中被重复追加 model。
            node_engine_config = dict(spec.engine_config)
            if (
                "model" not in node_engine_config
                and "model_path" not in node_engine_config
                and "model" not in user_layer
                and "model_path" not in user_layer
            ):
                # 没有模型 recipe 时只能使用请求中的模型名；这是最低优先级，
                # _resolve_multi_node 后续仍会让显式 user_layer 覆盖它。
                node_engine_config["model"] = model_name
            fallback_node_specs.append(spec._replace(engine_config=node_engine_config))

        # 统一复用正常模型 recipe 的多机解析流程：
        # 有运行时 IP 时选择当前 Pod 并注入；没有时生成 head/worker 占位视图。
        return (
            *_resolve_multi_node(
                fallback_node_specs,
                model_path=platform_path,
                user_layer=user_layer,
                feature_overrides=feature_overrides,
                feature_trace_sources=feature_trace_sources,
                accel_overrides=accel_layer,
                device_count=device_count,
                rank_ip=rank_ip,
                node_ips=node_ips,
                master_ip=master_ip,
                hardware=hardware,
                weights_path=weights_path,
                strategy_env_layer=strategy_env_layer,
                strategy_feature_inject_overrides=strategy_feature_inject_overrides,
            ),
            fallback_pattern,
        )

    # 当前场景未提供节点列表时，使用场景级 engine_config 生成普通引擎配置。
    scenario_engine_config = dict(platform_scenario.get("engine_config", {}))

    # 平台场景没有 model/model_path 时，用请求名补齐引擎必需的模型参数；
    # 如果平台或用户已经提供路径，则保留它们，不进行覆盖。
    if (
        "model" not in scenario_engine_config
        and "model_path" not in scenario_engine_config
        and "model" not in user_layer
        and "model_path" not in user_layer
    ):
        scenario_engine_config["model"] = model_name

    # 单段 fallback 也必须经过与正常 recipe 相同的 TP/DP 策略处理，
    # 这样 device_count 等用户输入仍能产生一致的 trace 和校验结果。
    _preflight_shrink_gate(scenario_engine_config, device_count, hardware, weights_path)
    strategy_overrides, strategy_notes = post_template_strategy(
        scenario_engine_config,
        {"device_count": device_count, "topology": topology},
    )
    # 按统一优先级合并平台默认值、策略覆盖、特性注入、智能加速和用户参数，
    # 并为每个最终参数保留来源链。
    engine_config_traces = _merge_engine_config_traces(
        scenario_engine_config,
        strategy_overrides,
        feature_overrides,
        feature_trace_sources,
        accel_layer,
        user_layer,
        model_layer_name="default_model",
        model_source_file=platform_path_str,
        scenario_prefix="engine_config",
        feature_inject_overrides=strategy_feature_inject_overrides,
    )

    # 环境变量单独合并，保持 engine_config 和 env 两条 trace 链互不混淆；
    # SmartQoS/OTLP/Metrics 等特性环境变量作为更高优先级覆盖层追加。
    env_layers = [
        MergeLayer("default_model", platform_env, platform_path_str, "env"),
    ]
    if strategy_env_layer:
        env_layers.append(
            MergeLayer(
                "strategy_feature_env",
                strategy_env_layer,
                "<strategy:feature_env_inject>",
                "strategy.feature_env_inject",
            )
        )
    return (
        engine_config_traces,
        trace_merge(env_layers),
        None,
        None,
        strategy_notes,
        fallback_pattern,
    )


_PD_OWNED_PARAMS = {
    "data_parallel_size",
    "data_parallel_rank",
    "data_parallel_start_rank",
    "data_parallel_size_local",
    "data_parallel_address",
    "data_parallel_rpc_port",
    "data_parallel_external_lb",
    "port",
    "kv_transfer_config",
}


def _overlay_pd_process_traces(
    base: Dict[str, TracedValue], overrides: Dict[str, Any], local_index: int
) -> Dict[str, TracedValue]:
    """在保留静态 recipe/user 完整 events 前提下追加 process 动态层。

    Args:
        base: role recipe 合并完成后的静态 traces。
        overrides: 当前 process 的 PD-owned 动态参数。
        local_index: 当前 Pod 内 process 序号。

    Returns:
        独立的 per-process traces。
    """
    result = {
        key: TracedValue(
            final_value=traced.final_value,
            final_layer=traced.final_layer,
            source_file=traced.source_file,
            source_path=traced.source_path,
            events=list(traced.events),
        )
        for key, traced in base.items()
    }
    for key, value in overrides.items():
        source_path = f"pd.processes[{local_index}].{key}"
        event = SourceEvent(
            action="override" if key in result else "set",
            layer="strategy_pd_process",
            value=value,
            source_file="<strategy:pd_process>",
            source_path=source_path,
        )
        final_value = value
        events = [event]
        if key in result:
            previous = result[key]
            if isinstance(previous.final_value, dict) and isinstance(value, dict):
                final_value = _deep_merge(previous.final_value, value)
            events = previous.events + [event]
        result[key] = TracedValue(
            final_value=final_value,
            final_layer="strategy_pd_process",
            source_file="<strategy:pd_process>",
            source_path=source_path,
            events=events,
        )
    return result


def _validate_pd_listener_conflicts(listeners: List[ListenerPlan]) -> None:
    """校验本 Pod 已知 listener 区间不重叠。

    Args:
        listeners: 已去除合法 share-group 重复项的 listener inventory。

    Raises:
        ValueError: 任一端口越界或不同 listener 区间相交。
    """
    occupied: List[tuple[int, int, str]] = []
    for listener in listeners:
        if listener.port_start is None or listener.port_end is None:
            continue
        if not 1 <= listener.port_start <= listener.port_end <= 65535:
            raise ValueError(f"PD listener {listener.name} 端口越界：{listener.port_start}..{listener.port_end}。")
        for start, end, name in occupied:
            if listener.port_start <= end and start <= listener.port_end:
                raise ValueError(
                    f"PD listener 冲突：{name}={start}..{end} 与 "
                    f"{listener.name}={listener.port_start}..{listener.port_end}。"
                )
        occupied.append((listener.port_start, listener.port_end, listener.name))


def _validate_pd_runtime_spec(runtime: PdRuntimeSpec, topology: ResolvedPdTopology) -> int:
    """校验 exact recipe 的闭集策略，并返回当前 Pod 进程数。

    静态类型只能帮助开发期检查；运行边界仍需 fail-fast，避免内部配置拼写错误
    静默关闭 endpoint、KV listener 或 connector identity。

    Raises:
        ValueError: 任一策略值未知、策略组合冲突或 KV port profile 不完整。
    """
    allowed_values = (
        (
            "topology_input_policy",
            runtime.topology_input_policy,
            {PD_TOPOLOGY_DERIVED_1P1D, PD_TOPOLOGY_EXPLICIT_ALLOCATION},
        ),
        ("process_layout", runtime.process_layout, {PD_PROCESS_LAYOUT_SINGLE, PD_PROCESS_LAYOUT_PER_LOCAL_RANK}),
        ("dp_launch_policy", runtime.dp_launch_policy, {PD_DP_LAUNCH_NONE, PD_DP_LAUNCH_EXTERNAL_RANK}),
        ("endpoint_policy", runtime.endpoint_policy, {PD_ENDPOINT_PER_PROCESS}),
        ("engine_id_policy", runtime.connector_profile.engine_id_policy, {PD_ENGINE_ID_OMIT, PD_ENGINE_ID_FROM_INDEX}),
        ("kv_port_policy.mode", runtime.connector_profile.kv_port_policy.mode, {PD_KV_PORT_FROM_INDEX}),
        (
            "kv_port_policy.listener_span",
            runtime.connector_profile.kv_port_policy.listener_span,
            {PD_KV_LISTENER_SINGLE, PD_KV_LISTENER_DEVICE_COUNT_PLUS_ONE},
        ),
        (
            "listener_owner_scope",
            runtime.connector_profile.listener_owner_scope,
            {PD_LISTENER_OWNER_PER_PROCESS, PD_LISTENER_OWNER_PER_POD_CONNECTOR_GROUP},
        ),
    )
    for field, value, allowed in allowed_values:
        if value not in allowed:
            raise ValueError(f"未知 PD {field}：{value!r}；允许值={sorted(allowed)}。")
    if runtime.topology_input_policy != topology.input_policy:
        raise ValueError(
            "PD runtime topology_input_policy 与 resolved topology 不一致："
            f"runtime={runtime.topology_input_policy!r}，resolved={topology.input_policy!r}。"
        )
    if runtime.connector_profile.kv_port_policy.base is None:
        raise ValueError("PD kv_port_policy.mode=from_pd_index 时必须提供 base。")
    if runtime.process_layout == PD_PROCESS_LAYOUT_SINGLE:
        if topology.dp_size_local != 1:
            raise ValueError("single_process layout 只接受 dp_size_local=1。")
        if runtime.dp_launch_policy != PD_DP_LAUNCH_NONE:
            raise ValueError("single_process layout 首期只接受 dp_launch_policy=none。")
        return 1
    if runtime.dp_launch_policy != PD_DP_LAUNCH_EXTERNAL_RANK:
        raise ValueError("per_local_dp_rank 首期只支持 external_rank。")
    return topology.dp_size_local


def _validate_pd_ambient_port(expected_ports: List[int]) -> None:
    """拒绝 ambient ENGINE_PORT 改写 exact endpoint profile。"""
    ambient_port = os.getenv("ENGINE_PORT")
    if ambient_port is None:
        return
    try:
        ambient_port_value = int(ambient_port, 10)
    except ValueError as exc:
        raise ValueError(f"PD ENGINE_PORT 必须是整数，当前值为 {ambient_port!r}。") from exc
    if ambient_port_value not in expected_ports or len(expected_ports) != 1:
        raise ValueError(f"PD ENGINE_PORT={ambient_port_value} 与 exact endpoint profile {expected_ports} 冲突。")


def _build_pd_process_overrides(
    topology: ResolvedPdTopology,
    runtime: PdRuntimeSpec,
    local_index: int,
    port: int,
) -> tuple[Dict[str, Any], int]:
    """构造一个 local process 的 PD-owned 参数覆盖和 KV listener 起始端口。"""
    role_shape = topology.prefill if topology.role is PdRole.PREFILL else topology.decode
    rank = topology.rank_start + local_index
    overrides: Dict[str, Any] = {"port": port}
    if topology.input_policy == PD_TOPOLOGY_DERIVED_1P1D:
        overrides["tensor_parallel_size"] = role_shape.tp_size
    if runtime.dp_launch_policy == PD_DP_LAUNCH_EXTERNAL_RANK:
        overrides.update(
            {
                "data_parallel_size": role_shape.dp_size,
                "data_parallel_rank": rank,
                "data_parallel_size_local": 1,
                "data_parallel_address": topology.placement.master_ip,
                "data_parallel_rpc_port": runtime.data_parallel_rpc_port,
                "data_parallel_external_lb": True,
            }
        )

    kv_policy = runtime.connector_profile.kv_port_policy
    assert kv_policy.base is not None
    kv_port = (
        kv_policy.base + topology.instance_index * kv_policy.instance_stride + local_index * kv_policy.process_stride
    )
    kv_overrides: Dict[str, Any] = {
        "kv_connector_extra_config": {
            "prefill": {"dp_size": topology.prefill.dp_size, "tp_size": topology.prefill.tp_size},
            "decode": {"dp_size": topology.decode.dp_size, "tp_size": topology.decode.tp_size},
        },
        "kv_port": kv_port,
    }
    if runtime.connector_profile.engine_id_policy == PD_ENGINE_ID_FROM_INDEX:
        kv_overrides["engine_id"] = str(topology.instance_index)
    overrides["kv_transfer_config"] = kv_overrides
    return overrides, kv_port


def _build_pd_process_env_traces(
    resolved: ResolvedConfig,
    local_index: int,
    visible_devices: tuple[int, ...],
) -> Dict[str, TracedValue]:
    """为一个 local process 追加可见设备环境变量 trace。"""
    visible_env_name = {"ascend": "ASCEND_RT_VISIBLE_DEVICES", "nvidia": "CUDA_VISIBLE_DEVICES"}.get(
        resolved.hardware.device
    )
    env_override = {visible_env_name: ",".join(str(item) for item in visible_devices)} if visible_env_name else {}
    return trace_merge(
        [
            MergeLayer(
                "model_scenario",
                {name: traced.final_value for name, traced in resolved.env_traces.items()},
                resolved.source_files[0],
                "pd_role_recipe.env",
            ),
            MergeLayer(
                "strategy_pd_process",
                env_override,
                "<strategy:pd_process>",
                f"pd.processes[{local_index}].env",
            ),
        ]
    )


def _build_pd_process_listeners(
    topology: ResolvedPdTopology,
    runtime: PdRuntimeSpec,
    local_index: int,
    rank: int,
    port: int,
    kv_port: int,
    device_count: int,
    shared_kv_added: bool,
) -> tuple[List[ListenerPlan], bool]:
    """构造一个 local process 的 API、DP RPC 和 KV listener inventory。"""
    listeners = [ListenerPlan("api", "0.0.0.0", port, port, f"process[{local_index}]")]
    if runtime.data_parallel_rpc_port is not None and rank == 0:
        listeners.append(
            ListenerPlan(
                "dp_rpc",
                str(topology.placement.master_ip),
                runtime.data_parallel_rpc_port,
                runtime.data_parallel_rpc_port,
                "instance_master",
            )
        )
    connector = runtime.connector_profile
    add_kv = connector.listener_owner_scope == PD_LISTENER_OWNER_PER_PROCESS or not shared_kv_added
    if not add_kv:
        return listeners, shared_kv_added
    span_end = kv_port
    if connector.kv_port_policy.listener_span == PD_KV_LISTENER_DEVICE_COUNT_PLUS_ONE:
        # 官方定义为闭区间 kv_port..kv_port+num_chips，因此共预留 device_count + 1 个端口。
        span_end = kv_port + device_count
    listeners.append(ListenerPlan("kv", "0.0.0.0", kv_port, span_end, connector.listener_owner_scope))
    return listeners, True


def _build_pd_process_plan(
    resolved: ResolvedConfig,
    runtime: PdRuntimeSpec,
    device_count: int,
) -> ProcessPlan:
    """从规范 topology 构造当前 Pod 唯一有序进程计划。

    Args:
        resolved: 已含 PD topology 和静态 role traces 的解析结果。
        runtime: exact role recipe 的固定 runtime spec。
        device_count: 当前 Pod 显式卡数。

    Returns:
        每进程独立 trace/env/argv/endpoint 与本 Pod listener inventory。

    Raises:
        ValueError: layout/policy 不兼容、ambient port 冲突或 listener 重叠。
    """
    # topology 已完成 role、Instance 成员、global/local DP closure 和卡数容量校验；
    # 本函数只把这份规范结果展开成当前 Pod 真正要启动的进程，不再推导并行策略。
    topology = resolved.pd_topology
    assert topology is not None
    role_shape = topology.prefill if topology.role is PdRole.PREFILL else topology.decode

    # exact runtime spec 决定“一个 Pod 启几条命令”。每条命令使用独立 backend port，
    # 因此 ambient ENGINE_PORT 不能再覆盖或模糊这份 endpoint profile。
    local_count = _validate_pd_runtime_spec(runtime, topology)
    expected_ports = [runtime.backend_port_base + index for index in range(local_count)]
    _validate_pd_ambient_port(expected_ports)

    listeners: List[ListenerPlan] = []
    processes: List[EngineProcessPlan] = []
    endpoints: List[str] = []
    shared_kv_added = False
    for local_index, port in enumerate(expected_ports):
        # local_index 同时确定 global DP rank、API endpoint、设备切片和 process trace 路径，
        # 这些值共同描述同一条 engine 命令，必须在一个循环中保持同序生成。
        rank = topology.rank_start + local_index
        host = topology.placement.rank_ip
        assert host is not None
        endpoint = f"{host}:{port}"

        # 静态 role trace 保留 recipe/feature/user 来源；PD-owned rank、端口和 connector
        # identity 作为 strategy_pd_process 追加，形成该进程专属的最终参数真相源。
        process_overrides, kv_port = _build_pd_process_overrides(topology, runtime, local_index, port)
        traces = _overlay_pd_process_traces(resolved.engine_config_traces, process_overrides, local_index)

        # 一个 local DP rank 独占连续 TP 卡组。例如 TP=4 时，local rank 1 使用 4..7。
        visible_start = local_index * role_shape.tp_size
        visible_devices = tuple(range(visible_start, visible_start + role_shape.tp_size))
        env_traces = _build_pd_process_env_traces(resolved, local_index, visible_devices)

        # listener inventory 是静态冲突模型，不负责真正 bind；DP rank 0 和共享 KV 组
        # 的 owner 规则在 helper 内收敛，避免每个 process 都伪造同一个 listener。
        process_listeners, shared_kv_added = _build_pd_process_listeners(
            topology, runtime, local_index, rank, port, kv_port, device_count, shared_kv_added
        )
        listeners.extend(process_listeners)
        endpoints.append(endpoint)
        processes.append(
            EngineProcessPlan(
                process_index=local_index,
                local_index=local_index,
                dp_rank=rank if runtime.dp_launch_policy != PD_DP_LAUNCH_NONE else None,
                visible_devices=visible_devices,
                advertised_endpoint=endpoint,
                engine_config_traces=traces,
                env_traces=env_traces,
                argv=build_argv(traces, engine=resolved.engine),
                listeners=process_listeners,
            )
        )

    # 先汇总再统一检查，才能发现 API、DP RPC 与 KV 预留区间之间的跨类型冲突。
    _validate_pd_listener_conflicts(listeners)
    return ProcessPlan(
        layout=runtime.process_layout,
        lifecycle="single" if local_count == 1 else "fail_together",
        processes=processes,
        endpoints=endpoints,
        listeners=listeners,
    )


def _resolve_pd_config(
    env: ResolvedEnv,
    target: Target,
    user_input: UserInput,
    device_count: int | None,
    pd_input: PdRuntimeInput,
) -> ResolvedConfig:
    """解析 exact PD recipe 并产出规范 topology。

    Args:
        env: 已解析配置根、硬件与 strict engine version。
        target: exact model variant、role topology 与 engine。
        user_input: 用户覆盖和特性开关。
        device_count: MaaS 显式卡数。
        pd_input: 当前 Pod 已规范化 PD 输入。

    Returns:
        已展开唯一 ``ProcessPlan`` 的 PD ``ResolvedConfig``；顶层 traces 已清空，执行方按 process 消费。

    Raises:
        ValueError: topology/role 不一致、accel 开启、PD-owned 用户覆盖或 recipe 非法。
        FileNotFoundError: exact model variant/config asset 缺失。
    """
    # PD_ROLE 是当前 Pod 的事实，Target.topology 是大策略层的判定结果；两者必须一致，
    # 否则后续可能加载错误 role recipe 并生成方向相反的 KV connector。
    expected_topology = {
        "P": Topology.PD_PREFILL,
        "D": Topology.PD_DECODE,
    }[pd_input.role.value]
    if target.topology is not expected_topology:
        raise ValueError(f"PD role/topology 不一致：role={pd_input.role.value}，topology={target.topology.value}。")

    # 首期 PD 的 rank、卡组和 connector identity 由 ProcessPlan 独占。禁止 accel 再次
    # 改写这些字段，也禁止 user_cli 绕过 trace ownership 覆盖 PD-owned 参数。
    accel_switches = collect_accel_switches(os.environ)
    enabled_accel = sorted(
        name for name, value in accel_switches.items() if name.endswith("_enabled") and value is True
    )
    if enabled_accel:
        raise ValueError(f"PD 首期不支持 wings-accel 开关：{enabled_accel}。")

    user_layer = user_input.cli_overrides or {}
    conflicts = sorted(_PD_OWNED_PARAMS.intersection(user_layer))
    if conflicts:
        raise ValueError(f"PD-owned 参数不允许 user_cli 覆盖：{conflicts}。")

    # PD 只接受 exact engine version 和 exact model variant。recipe 是已验收的命令形状，
    # 不能像标准推理一样通过版本或模型 fallback 换成另一份拓扑配置。
    family_dir = resolve_family_dir(
        env.config_root,
        target.engine,
        env.hardware.hardware_family,
        env.engine_version.resolved,
        has_version_dir=env.engine_version.has_version_dir,
    )
    model_data, model_path, matched = load_model_config(
        env.config_root,
        family_dir,
        target.engine,
        env.engine_version.resolved,
        target.model_name,
        has_version_dir=env.engine_version.has_version_dir,
        exact_variant_only=True,
    )
    assert model_data is not None and model_path is not None
    # FeatureOverlay 沿用标准推理语义，但必须在 per-process runtime 层之前进入静态
    # role trace，确保每条进程命令都继承同一份 feature 决策与来源事件。
    normalized_features, reasoning_resolution, reasoning_table_source = _prepare_feature_context(
        env.config_root,
        target.model_name,
        target.engine,
        model_data,
        bool((user_input.feature_switches or {}).get("enable_auto_think_choice")),
    )
    reasoning_source_file = ""
    reasoning_source_path = ""
    if reasoning_resolution is not None and reasoning_resolution.spec:
        reasoning_source_file = reasoning_resolution.source
        reasoning_source_path = reasoning_resolution.spec.source
    elif isinstance(normalized_features.get("reasoning"), dict):
        reasoning_source_file = str(model_path)
        reasoning_source_path = "features.reasoning.args"
    feature_result = feature_overlay_transform(
        {},
        {
            "features": normalized_features,
            "feature_switches": user_input.feature_switches or {},
            "reasoning_source_file": reasoning_source_file,
            "reasoning_source_path": reasoning_source_path,
        },
    )
    feature_overrides = feature_result.overrides
    feature_trace_sources = feature_result.trace_sources
    feature_notes = feature_result.notes
    # 输入是否携带 MaaS 六字段决定 topology policy；recipe 选择器会反向校验该 policy
    # 是否与 YAML 的 P/D parallel shape 相符，planner 再完成 placement/rank/容量闭合。
    input_policy = "explicit_allocation" if pd_input.explicit_topology is not None else "derived_1p1d"
    pair = select_pd_recipe_pair(model_data, input_policy)
    role_recipe = pair[pd_input.role]
    pd_topology = resolve_pd_topology(pd_input, pair, device_count)
    rank_ip = pd_topology.placement.rank_ip
    assert rank_ip is not None
    # recipe env 保留可审计的字面占位符，只有当前 Pod placement 明确后才注入真实 IP。
    network_env_overrides = substitute_literal_placeholders(
        role_recipe.env,
        rank_ip=rank_ip,
        master_ip=pd_topology.placement.master_ip,
    )

    # 先形成 role 级静态 trace。这里不写 local rank、backend/KV port 或设备可见性；
    # 这些随进程变化的值只能由 _build_pd_process_plan 追加 strategy_pd_process 层。
    engine_layers = [
        MergeLayer("builtin_default", _BUILTIN_DEFAULTS, "<builtin>", "engine_config"),
        MergeLayer(
            "model_scenario",
            role_recipe.engine_config,
            str(model_path),
            f"{role_recipe.source_prefix}.engine_config",
        ),
        MergeLayer(
            "strategy_feature",
            feature_overrides,
            "<strategy:feature>",
            "strategy.feature",
            feature_trace_sources,
        ),
    ]
    if user_layer:
        engine_layers.append(MergeLayer("user_cli", user_layer, "<user_cli>", "user_cli"))
    engine_traces = trace_merge(engine_layers)
    env_layers = [
        MergeLayer(
            "model_scenario",
            role_recipe.env,
            str(model_path),
            f"{role_recipe.source_prefix}.env",
        )
    ]
    if network_env_overrides:
        env_layers.append(
            MergeLayer(
                "strategy_topology_inject",
                network_env_overrides,
                "<strategy:pd_network>",
                "pd.network.env",
            )
        )
    env_traces = trace_merge(env_layers)
    runtime_commands = runtime_var_commands(role_recipe.engine_config, role_recipe.env)
    notes = {
        "matched_model_yaml": str(model_path),
        "matched_name_pattern": matched,
        "fallback": "false",
        "pd_recipe": role_recipe.strategy_name,
        "pd_topology_input_policy": input_policy,
        "pd_accel": "disabled",
        "device_count": str(device_count),
    }
    if input_policy == "derived_1p1d":
        notes.update(
            {
                "pd_tp_source": "device_count",
                "pd_peer_device_count_validation": "maas_asserted_not_locally_observable",
            }
        )
    notes.update(feature_notes)
    if reasoning_resolution is not None:
        notes["reasoning.status"] = reasoning_resolution.status
        notes["reasoning.source"] = reasoning_resolution.source
        notes["reasoning.match_level"] = reasoning_resolution.match_level
        notes["reasoning.reason"] = reasoning_resolution.reason or ""
    if reasoning_table_source:
        notes["reasoning.table_source"] = reasoning_table_source
    if env.engine_version.has_version_dir:
        notes.update(
            {
                "requested_version": env.engine_version.requested or "<none>",
                "resolved_version": env.engine_version.resolved,
                "version_is_fallback": "false",
            }
        )
    # 临时 ResolvedConfig 承载 role 级 trace 和规范 topology，作为 ProcessPlan 的输入。
    # 生成计划后，执行、渲染和审计都切换到 process_plan 中的 per-process 数据。
    resolved = ResolvedConfig(
        topology=target.topology,
        hardware=env.hardware,
        engine=target.engine,
        engine_version=env.engine_version,
        engine_config_traces=engine_traces,
        env_traces=env_traces,
        source_files=[str(model_path), *([reasoning_table_source] if reasoning_table_source else [])],
        system_setup=SystemSetup(
            commands=runtime_commands,
            source_file="<strategy:pd_network>",
            source_path="pd.network.runtime_commands",
        )
        if runtime_commands
        else None,
        resolution_notes=notes,
        user_cli_params=_build_user_cli_audit_entries(user_layer, user_input.cli_dropped),
        accel=AccelResult(),
        pd_topology=pd_topology,
    )
    if device_count is None:
        raise ValueError("PD 场景必须显式提供 device_count。")
    resolved.process_plan = _build_pd_process_plan(resolved, role_recipe.runtime, device_count)
    # 顶层 trace 描述的是展开前的 role 公共配置，不对应任何一条完整命令。清空后可强制
    # 所有消费者读取 process_plan，避免误把 processes[0] 的 rank/端口当成整个 Pod 的配置。
    resolved.engine_config_traces = {}
    resolved.env_traces = {}
    return resolved


def resolve_config(
    env: ResolvedEnv,
    target: Target,
    user_input: UserInput = UserInput(),
    device_count: int | None = None,
    placement: ClusterPlacement | None = None,
    pd_input: PdRuntimeInput | None = None,
) -> ResolvedConfig:
    """端到端配置解析主入口。

    执行:
    1. 加载 default_model.yaml 的 scenarios.{topology} 默认策略
    2. 加载 model yaml 的 scenarios.{topology}.engine_config(multi_node 为 nodes[])
    3. trace-aware 多层合并 (builtin_default → model_scenario → strategy → user_cli)
    4. 写入 resolution_notes: 版本查找轨迹 + 模型匹配轨迹
    5. 记录 device_count 到 resolution_notes;单节点 DeviceCountTransform 协调 DP
    6. multi_node:逐节点深合并;有运行时上下文(rank_ip+node_ips)时选本 Pod 节点
       升顶层可执行 + DP 调整 + 占位填充,否则产全集群占位视图
    7. PD 分离(pd_prefill/pd_decode):需规范化 pd_input,进入 ``_resolve_pd_config``
       (exact recipe → 规范 topology → ProcessPlan);standalone / multi_node 走原路径。
    8. 组装 ResolvedConfig

    Args:
        env: 已解析环境 —— config_root(已定位真实根)/ hardware / engine_version。
        target: 解析目标 —— model_name / topology(大策略层判定)/ engine。
        user_input: 用户 CLI 意图 —— cli_overrides(已翻译为引擎参数名)/ cli_dropped(审计)/
            feature_switches(驱动小策略层 FeatureOverlay 从 model.yaml ``features`` 块拼特性参数)。
        device_count: 下发卡数(全程规模:并行协调 / 单机 TP 收缩;None=不触发)。
        placement: 分布式集群寻址(multi_node/PD 选 node、判定 head、替换占位符;
            None=单机/无运行时上下文→占位)。
        pd_input: PD 场景规范化输入(role / topology / placement);仅
            ``Topology.PD_PREFILL`` / ``PD_DECODE`` 需要,缺失则 fail-fast。

    Returns:
        ``ResolvedConfig``:包含最终 traces、resolution_notes、多机场景信息与审计附加字段。

    Raises:
        ValueError: PD topology 缺规范化 ``pd_input`` / 标准 multi_node 选 node 强校验失败 /
            DP 协调越界(详见 strategy.topology_inject / ``_resolve_pd_config``)。
        NotImplementedError: 除 standalone / multi_node / PD 之外其余 topology(往后做)。
    """
    # 解包成局部变量:下方主体逻辑沿用既有命名,签名收口为请求对象但行为不变。
    config_root = env.config_root
    hardware = env.hardware
    engine_version = env.engine_version
    model_name = target.model_name
    topology = target.topology
    engine = target.engine
    user_cli_overrides = user_input.cli_overrides
    user_cli_dropped = user_input.cli_dropped
    feature_switches = user_input.feature_switches
    # device_count 是全程标量入参;分布式集群寻址三件从 placement 取(单机/无上下文 placement=None → 三者 None)。
    _placement = placement or ClusterPlacement()
    rank_ip = _placement.rank_ip
    node_ips = _placement.node_ips
    master_ip = _placement.master_ip

    # topology 由大策略层(pre_template_strategy,cli 入口)推导后传入;此处纯消费。
    if topology in (Topology.PD_PREFILL, Topology.PD_DECODE):
        if pd_input is None:
            raise ValueError(f"Topology '{topology.value}' 缺少规范化 pd_input。")
        return _resolve_pd_config(env, target, user_input, device_count, pd_input)
    if topology not in (Topology.STANDALONE, Topology.MULTI_NODE):
        raise NotImplementedError(f"Topology '{topology.value}' not implemented.")

    # 把下发的 hardware_family(资源域词汇,可能带显存后缀 / 大小写不一)解析成实际 config 目录名。
    # 单一判定点:目录定位(platform / model)与 accel gpu_type 都用这个落地目录名;
    # hardware.hardware_family 保留下发原值(审计 / 日志显示)。
    resolved_family_dir = resolve_family_dir(
        config_root,
        engine,
        hardware.hardware_family,
        engine_version.resolved,
        has_version_dir=engine_version.has_version_dir,
    )

    # 1. 加载平台默认配置(缺失返回空 dict + None path)
    platform_data, platform_path = load_platform_config(
        config_root,
        resolved_family_dir,
        engine,
        engine_version.resolved,
        has_version_dir=engine_version.has_version_dir,
    )
    platform_absent = platform_path is None
    platform_path_str = str(platform_path) if platform_path is not None else "<absent>"
    # 2. 加载模型配置(ret: data|None, yaml_path|None, matched_pattern)
    model_data, model_path, matched_pattern = load_model_config(
        config_root,
        resolved_family_dir,
        engine,
        engine_version.resolved,
        model_name,
        has_version_dir=engine_version.has_version_dir,
    )

    # ── 3. 组装各合并输入层(user_cli / feature / accel)+ 版本校验 ──
    user_layer = user_cli_overrides or {}
    # 模型权重目录(--model-path,经 CLITranslator 落 user_cli 的 model/model_path 键);TP 收缩前置闸会读取它。
    weights_path = user_layer.get("model") or user_layer.get("model_path")

    # 所有模型特性先复制，再由各特性自己的标准化步骤处理。
    # 当前 reasoning 使用公共能力表；未来特性可在同一 helper/流水线中独立接入。
    normalized_features, reasoning_resolution, reasoning_table_source = _prepare_feature_context(
        config_root, model_name, engine, model_data,
        bool((feature_switches or {}).get("enable_auto_think_choice")),
    )
    reasoning_source_file = ""
    reasoning_source_path = ""
    if reasoning_resolution is not None and reasoning_resolution.spec:
        reasoning_source_file = reasoning_resolution.source
        reasoning_source_path = reasoning_resolution.spec.source
    elif isinstance((normalized_features or {}).get("reasoning"), dict):
        reasoning_source_file = str(model_path or "<model_yaml>")
        reasoning_source_path = "features.reasoning.args"
    feature_result = feature_overlay_transform(
        {},
        {
            "features": normalized_features,
            "feature_switches": feature_switches or {},
            "reasoning_source_file": reasoning_source_file,
            "reasoning_source_path": reasoning_source_path,
        },
    )
    feature_overrides = feature_result.overrides
    feature_trace_sources = feature_result.trace_sources
    feature_notes = feature_result.notes

    # 特性注入层（SmartQoS/EnableTrace/Metrics）：与模板内容无关，只依赖 feature_switches 和 engine。
    # 像 feature_overlay_transform 一样只调用一次，结果供 fallback/standalone/multi_node 三条路径共用。
    strategy_feature_inject_overrides, strategy_env_layer, feature_inject_notes = feature_inject_transform(
        feature_switches or {},
        engine,
    )

    user_cli_audit_entries = _build_user_cli_audit_entries(user_layer, user_cli_dropped)
    platform_env = platform_data.get("platform_env", {})

    # wings-accel(智能加速)委托:按开关取加速产出(结构化 engine_config / env / scheme)。
    # 在 trace_merge **之前**计算,把 accel.engine_config 作为 strategy_accel 合并层并入引擎参数,
    # 层序为 recipe < accel < user_cli。
    # 复用 _deep_merge 深合并 + 同名去重 + 每参带 trace。模块未接通/关闭/无资产 → 空 AccelResult
    # (层为空 dict,trace_merge 遍历零 key,non-accel 路径零影响)。
    # model 定位以 model_name 为准(accel 内部定位 yaml),model_path 仅兜底,故传 None。
    # 预读 recipe 的 TP/DP 透传给 accel:smart-accel YAML 常无 scenarios(KV 内存 auto 估算需要 TP/DP,
    # 否则 worker_count 退化为 1,available 估算偏大)。覆盖所有 scenario 形态(单段/nodes[]/head·worker):
    # - multi_node 形态按 rank_ip+node_ips+master_ip 选本 Pod node 的 TP/DP(head 与 worker 可不同);
    # - 无运行时 IP 上下文(占位加载)退化取 head;recipe 缺失/字段缺失 → 0(accel 内部兜底 1)。
    recipe_tp, recipe_dp = _peek_recipe_parallelism(
        model_data, topology,
        rank_ip=rank_ip, node_ips=node_ips, master_ip=master_ip,
    )
    accel = apply_smart_accel(
        hardware_family=resolved_family_dir,
        gpu_count=device_count,
        model_path=None,
        model_name=model_name,
        engine=engine,
        # smart-accel 资产按【实际引擎版本 = ENGINE_VERSION】命名(如 v0.23.0);用 requested,
        # 不用 resolved —— resolved 是 wings-control config 目录版本,引擎无版本目录时(如 vllm)为空。
        engine_version=engine_version.requested or engine_version.resolved,
        config_root=str(config_root),
        pd_role=os.getenv("PD_ROLE"),
        # topology 由大策略层(pre_template)推导(已聚合 PD_ROLE/DISTRIBUTED/NODE_IPS),
        # 直接传入;适配层不再从 env 重复推导(消除 _resolve_topology 滥用 env.get)。
        topology=topology.value,
        tp_size=recipe_tp,
        dp_size=recipe_dp,
    )
    accel_layer = accel.engine_config  # strategy_accel 合并层(空 dict = 无产出 → trace_merge no-op)

    no_model_fallback = model_data is None or model_path is None
    actual_engine_version_for_min = engine_version.resolved or engine_version.requested
    # 记录 min 版本校验使用的版本来源(写入 resolution_notes / audit,供排查解释):
    #   有 resolved 用 "resolved";否则有 requested 用 "requested";两者皆空为 "unset"。
    if engine_version.resolved:
        min_check_version_source = "resolved"
    elif engine_version.requested:
        min_check_version_source = "requested"
    else:
        min_check_version_source = "unset"
    min_engine_check = _evaluate_min_engine_version(model_data, actual_engine_version_for_min)
    selected_strategy = None
    strategy_selection_source = ""
    strategy_default_candidates: List[str] = []
    strategy_notes: dict = {}
    nodes: List[ResolvedNode] | None = None
    # ── 4. 按 topology / 是否命中 recipe 合并出 engine_config / env traces ──
    #      fallback(无 recipe)/ standalone 命中 / multi_node 逐节点,三条路径。
    if no_model_fallback:
        logger.warning("无 model recipe,按平台基线兜底")
        (
            engine_config_traces,
            env_traces,
            system_setup,
            nodes,
            strategy_notes,
            matched_pattern,
        ) = _resolve_platform_fallback(
            platform_data=platform_data,
            platform_path=platform_path,
            platform_env=platform_env,
            topology=topology,
            model_name=model_name,
            user_layer=user_layer,
            feature_overrides=feature_overrides,
            feature_trace_sources=feature_trace_sources,
            accel_layer=accel_layer,
            strategy_env_layer=strategy_env_layer,
            strategy_feature_inject_overrides=strategy_feature_inject_overrides,
            device_count=device_count,
            hardware=hardware,
            weights_path=weights_path,
            rank_ip=rank_ip,
            node_ips=node_ips,
            master_ip=master_ip,
        )
    else:
        # pod_count 供 head/worker 形态展开:有运行时 NODE_IPS 用其长度,否则交 _select_scenario 兜底(nnodes/2)
        scenario = _select_scenario(model_data, topology, pod_count=(len(node_ips) if node_ips else None))
        selected_strategy = scenario.get("selected_strategy")
        strategy_selection_source = scenario.get("strategy_selection_source", "")
        strategy_default_candidates = scenario.get("strategy_default_candidates", [])

        node_specs = scenario.get("nodes")
        if node_specs:
            # multi_node:逐节点深合并 + 选 node/注入(详见 _resolve_multi_node)。
            engine_config_traces, env_traces, system_setup, nodes, strategy_notes = _resolve_multi_node(
                node_specs,
                model_path=model_path,
                user_layer=user_layer,
                feature_overrides=feature_overrides,
                feature_trace_sources=feature_trace_sources,
                accel_overrides=accel_layer,
                device_count=device_count,
                rank_ip=rank_ip,
                node_ips=node_ips,
                master_ip=master_ip,
                hardware=hardware,
                weights_path=weights_path,
                strategy_env_layer=strategy_env_layer,
                strategy_feature_inject_overrides=strategy_feature_inject_overrides,
            )
        else:
            scenario_engine_config = scenario["engine_config"]
            _preflight_shrink_gate(scenario_engine_config, device_count, hardware, weights_path)
            strategy_overrides, strategy_notes = post_template_strategy(
                scenario_engine_config,
                {"device_count": device_count, "topology": topology},
            )
            scenario_env = scenario["env"]
            scenario_engine_config_source_prefix = scenario["engine_config_source_prefix"]
            scenario_env_source_prefix = scenario["env_source_prefix"]

            # 命中 model:builtin_default + model_scenario + strategy + accel + user_cli(不叠 default_model)
            engine_config_traces = _merge_engine_config_traces(
                scenario_engine_config,
                strategy_overrides,
                feature_overrides,
                feature_trace_sources,
                accel_layer,
                user_layer,
                model_layer_name="model_scenario",
                model_source_file=str(model_path),
                scenario_prefix=scenario_engine_config_source_prefix,
                feature_inject_overrides=strategy_feature_inject_overrides,
            )

            # env merge: model 层 + 特性 env 注入层
            env_layers = [
                MergeLayer("model_scenario", scenario_env, str(model_path), scenario_env_source_prefix),
            ]
            if strategy_env_layer:
                env_layers.append(
                    MergeLayer(
                        "strategy_feature_env",
                        strategy_env_layer,
                        "<strategy:feature_env_inject>",
                        "strategy.feature_env_inject",
                    ),
                )
            env_traces = trace_merge(env_layers)

            # system_setup 构建(仅场景层,从空集合起)
            system_setup = _build_system_setup(
                scenario["system_setup"],
                str(model_path),
                scenario["system_setup_source_prefix"],
            )

    # FlashComm1 / DSA-CP 仅支持 TP>=2；在所有 merge 层完成后统一执行最终约束策略。
    # 多机占位节点分别应用，保证占位视图与运行时选中节点的行为一致。
    post_merge_notes: dict[str, str] = {}
    if nodes:
        for node in nodes:
            result = apply_post_merge_strategy(
                node.engine_config_traces,
                node.env_traces,
                engine=engine,
            )
            node.engine_config_traces = result.engine_config_traces
            node.env_traces = result.env_traces
            if result.notes:
                post_merge_notes.update(result.notes)
    else:
        result = apply_post_merge_strategy(
            engine_config_traces,
            env_traces,
            engine=engine,
        )
        engine_config_traces = result.engine_config_traces
        env_traces = result.env_traces
        post_merge_notes.update(result.notes)

    # ── 5. 组装结果:source_files + resolution_notes(查找/合并轨迹)+ ResolvedConfig ──
    # 仅将实际存在的文件加入 source_files
    source_files: List[str] = []
    if reasoning_table_source:
        source_files.append(reasoning_table_source)
    if not platform_absent:
        source_files.append(platform_path_str)
    if model_path is not None:
        source_files.append(str(model_path))

    # 解析注记:platform_default 缺失标记 + 查找轨迹
    resolution_notes: Dict[str, str] = {}
    if platform_absent:
        resolution_notes["platform_default"] = "absent"

    # 查找轨迹 — 版本解析结果
    if engine_version.has_version_dir:
        resolution_notes["resolved_version_dir"] = str(config_root / "engines" / engine / f"v{engine_version.resolved}")
        resolution_notes["version_is_fallback"] = "true" if engine_version.is_fallback else "false"
        resolution_notes["requested_version"] = engine_version.requested or "<none>"
        resolution_notes["resolved_version"] = engine_version.resolved

    # 查找轨迹 — 模型匹配结果
    resolution_notes["matched_model_yaml"] = str(model_path) if model_path is not None else platform_path_str
    if reasoning_resolution is not None:
        resolution_notes["reasoning.status"] = reasoning_resolution.status
        resolution_notes["reasoning.source"] = reasoning_resolution.source
        resolution_notes["reasoning.match_level"] = reasoning_resolution.match_level
        resolution_notes["reasoning.reason"] = reasoning_resolution.reason or ""
    if reasoning_table_source:
        resolution_notes["reasoning.table_source"] = reasoning_table_source
    resolution_notes["matched_name_pattern"] = matched_pattern
    resolution_notes["fallback"] = no_model_fallback
    model_schema_version = (
        str(model_data.get("schema_version"))
        if isinstance(model_data, dict) and model_data.get("schema_version") is not None
        else "unset"
    )
    default_model_schema_version = (
        str(platform_data.get("schema_version"))
        if isinstance(platform_data, dict) and platform_data.get("schema_version") is not None
        else "unset"
    )
    resolution_notes["model_schema_version"] = model_schema_version
    resolution_notes["default_model_schema_version"] = default_model_schema_version
    resolution_notes["wings_ctl_version"] = WINGS_CTL_VERSION
    resolution_notes["device_count"] = str(device_count) if device_count is not None else "unset"
    resolution_notes["device_count_source"] = "provided" if device_count is not None else "unset"
    # 小策略层 DeviceCountTransform 协调摘要(template_tp/dp、resolved_dp、status)
    resolution_notes.update(strategy_notes)
    resolution_notes.update(post_merge_notes)
    resolution_notes.update(feature_notes)  # 特性附加/跳过摘要(feature_overlay)
    resolution_notes.update(feature_inject_notes)  # SmartQoS/EnableTrace/Metrics 注入摘要
    resolution_notes["min_engine_version"] = min_engine_check["min_engine_version"]
    resolution_notes["engine_version_for_min_check"] = min_engine_check["engine_version_for_min_check"]
    resolution_notes["engine_version_for_min_check_source"] = min_check_version_source
    resolution_notes["min_engine_version_check"] = min_engine_check["min_engine_version_check"]
    resolution_notes["min_engine_version_check_reason"] = min_engine_check["min_engine_version_check_reason"]
    if selected_strategy:
        resolution_notes["selected_strategy"] = selected_strategy
        resolution_notes["strategy_selection_source"] = strategy_selection_source
        resolution_notes["strategy_default_candidates"] = ",".join(strategy_default_candidates)

    # wings-accel:engine_config 已作为 strategy_accel 合并层并入上方 engine_config_traces。
    # 这里仅把 accel 结构挂到 ResolvedConfig,供 env 渲染与 audit 摘要使用。
    return ResolvedConfig(
        topology=topology,
        hardware=hardware,
        engine=engine,
        engine_version=engine_version,
        engine_config_traces=engine_config_traces,
        env_traces=env_traces,
        source_files=source_files,
        system_setup=system_setup,
        resolution_notes=resolution_notes,
        user_cli_params=user_cli_audit_entries,
        nodes=nodes,
        accel=accel,
    )


# ─── Backward-compat aliases for tests that import private names ─────────
_load_model_config = load_model_config
_load_platform_config = load_platform_config
