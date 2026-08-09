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
from wings_ctl.accel.smart_accel import apply_smart_accel
from wings_ctl.core.constants import DEFAULT_ENGINE_PORT
from wings_ctl.core.models import (
    ClusterPlacement,
    HardwareContext,
    ResolvedConfig,
    ResolvedEnv,
    ResolvedNode,
    SourceEvent,
    SystemSetup,
    Target,
    TracedValue,
    UserInput,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import _parse_version_tuple
from wings_ctl.loaders.locator import load_model_config, load_platform_config, resolve_family_dir
from wings_ctl.strategy.parallelism import check_capacity, dp_start_rank
from wings_ctl.strategy.feature_overlay import feature_overlay_transform
from wings_ctl.strategy.feature_inject import feature_inject_transform
from wings_ctl.strategy.post_template import post_template_strategy
from wings_ctl.weight.reader import read_num_attention_heads, resolve_weight_bytes
from wings_ctl.strategy.topology_inject import (
    LAYOUT_TP_ACROSS,
    coordinate_parallelism,
    detect_layout,
    runtime_var_commands,
    select_node,
    substitute_literal_placeholders,
)

logger = logging.getLogger(__name__)

# 内置最小默认值(最低优先级层):模板/用户都没给时由 wings-control 兜底。
# 引擎无关数据常量。模板有→覆盖;用户传→最高优先级覆盖。
# 注意：这里使用backend_port=17000，因为start_command.sh中的engine应该监听backend端口
# DEFAULT_ENGINE_PORT 单点定义在 core.constants(port_plan 复用同一常量,消除双写);
# 顶部已 import 并 re-export,保持既有 `from ...config_resolver import DEFAULT_ENGINE_PORT` 不变。
_BUILTIN_DEFAULTS: Dict[str, Any] = {"host": "0.0.0.0", "port": DEFAULT_ENGINE_PORT}


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
        engine_config_source_prefix / env_source_prefix / system_setup_source_prefix:
            各块在 yaml 中的来源路径前缀(trace 溯源用)。
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


def _from_head_worker(
    strategy: Dict[str, Any], strategy_prefix: str, pod_count: int | None
) -> List[NodeSpec]:
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
        if detect_layout(ec) == LAYOUT_TP_ACROSS:       # TP 跨 Pod
            ec["node_rank"] = i
        elif "data_parallel_start_rank" in ec:          # DP 跨 Pod(start_rank 公式复用公共函数)
            ec["data_parallel_start_rank"] = dp_start_rank(i, ec.get("data_parallel_size_local") or 1)
        specs.append(_make_node_spec(
            {"engine_config": ec, "env": worker.get("env"), "system_setup": worker.get("system_setup")},
            role="worker", index=i, node_prefix=f"{strategy_prefix}.worker",
        ))
    return specs


def normalize_nodes(
    strategy: Dict[str, Any], strategy_prefix: str, pod_count: int | None
) -> List[NodeSpec] | None:
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
    if isinstance(nodes_raw, list):                     # nodes[] 形态:逐项枚举(ascend 及大量 nvidia recipe)
        specs = _from_nodes_list(nodes_raw, strategy_prefix)
        logger.info("multi_node 形态归一:nodes[] → %d 节点", len(specs))
        return specs
    if "head" in strategy or "worker" in strategy:      # head/worker 形态:复用展开(当前见于 nvidia)
        if "head" not in strategy:
            raise ValueError(
                f"multi_node 形态含 'worker' 但缺 'head',无法确定主节点:strategy 键={sorted(strategy)}"
            )
        specs = _from_head_worker(strategy, strategy_prefix, pod_count)
        logger.info("multi_node 形态归一:head/worker → %d 节点", len(specs))
        return specs
    return None                                         # 非多段形态 → 交调用方按单段处理


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
    """
    name: str
    data: Dict[str, Any]
    source_file: str
    source_path_prefix: str


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
            source_path = f"{path_prefix}.{key}" if path_prefix else key
            event = SourceEvent(
                action="set" if key not in merged else "override",
                layer=layer_name,
                value=value,
                source_file=src_file,
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
                        source_file=src_file,
                        source_path=source_path,
                        events=existing.events + [event],
                    )
                else:
                    # 标量/list: 整体替换
                    merged[key] = TracedValue(
                        final_value=value,
                        final_layer=layer_name,
                        source_file=src_file,
                        source_path=source_path,
                        events=existing.events + [event],
                    )
            else:
                merged[key] = TracedValue(
                    final_value=value,
                    final_layer=layer_name,
                    source_file=src_file,
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
        accel_overrides: wings-accel 产出的 engine_config 合并层(模型级,对每个节点统一应用;
            排 strategy_feature 后、user_cli 前 → recipe < accel < user_cli;空=无加速产出)。
        device_count: 本 Pod 卡数(None 不触发多机 DP 协调)。
        rank_ip / node_ips / master_ip: 运行时上下文;``rank_ip and node_ips`` 在场时走注入路径。
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
                    "strategy_topology_inject", override,
                    "<strategy:topology_inject>", "strategy.topology_inject",
                )
            )
        if strategy_env_layer:
            merge_layers.append(
                MergeLayer("strategy_feature_env", strategy_env_layer, "<strategy:feature_env_inject>", "strategy.feature_env_inject"),
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
            spec.engine_config, device_count=device_count, pod_count=pod_count, index=sel.index,
        )
        # 字面占位替换($local_ip/$node0_ip → 真实 IP),单独记一层 trace。
        # argv 里需要是字面值;$nic_name 这类运行时变量保留给 shell 展开。
        ec_inject = substitute_literal_placeholders(spec.engine_config, rank_ip=rank_ip, master_ip=master_ip)
        env_inject = substitute_literal_placeholders(spec.env, rank_ip=rank_ip, master_ip=master_ip)
        ec_traces = _ec_traces(spec, extra_layers=[
            MergeLayer("strategy_multinode_dp", dp_override, "<strategy:multinode_dp>", "strategy.multinode_dp"),
            MergeLayer("strategy_topology_inject", ec_inject, "<strategy:topology_inject>", "strategy.topology_inject"),
            MergeLayer("strategy_feature", feature_overrides, "<strategy:feature>", "strategy.feature"),
            MergeLayer("strategy_feature_inject", strategy_feature_inject_overrides or {}, "<strategy:feature_inject>", "strategy.feature_inject"),
            MergeLayer("strategy_accel", accel_overrides, "<wings-accel>", "strategy.accel"),
        ])
        env_traces = _env_traces(spec, override=env_inject)

        # system_setup:commands 仅保留运行时 nic 探测(若被 env 引用);特权 sysctls/sysfs 原样(渲染层注释)。
        raw_ss = spec.system_setup
        nic_cmds = runtime_var_commands(spec.engine_config, spec.env)
        system_setup = _build_system_setup(
            raw_ss, model_path_str, spec.system_setup_source_prefix, commands_override=nic_cmds,
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
            MergeLayer("strategy_feature", feature_overrides, "<strategy:feature>", "strategy.feature"),
            MergeLayer("strategy_feature_inject", strategy_feature_inject_overrides or {}, "<strategy:feature_inject>", "strategy.feature_inject"),
            MergeLayer("strategy_accel", accel_overrides, "<wings-accel>", "strategy.accel"),
        ]
        engine_config_traces = _ec_traces(spec, extra_layers=extra_layers)
        env_traces = _env_traces(spec)
        system_setup = _build_system_setup(
            spec.system_setup, model_path_str, spec.system_setup_source_prefix,
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
        len(resolved_nodes), notes["multi_node_roles"],
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
        device_count, int(gpu_mem_gb), weight_bytes,
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
    entries: List[Dict[str, Any]] = [
        {"key": k, "value": v, "status": "applied"}
        for k, v in user_layer.items()
    ]
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
    layers: list[MergeLayer] = [
        MergeLayer("builtin_default", _BUILTIN_DEFAULTS, "<builtin_default>", "builtin_default"),
        MergeLayer(model_layer_name, scenario_engine_config, model_source_file, scenario_prefix),
        MergeLayer("strategy_device_count", strategy_overrides, "<strategy:device_count>", "strategy.device_count"),
        MergeLayer("strategy_feature", feature_overrides, "<strategy:feature>", "strategy.feature"),
    ]
    if feature_inject_overrides:
        layers.append(
            MergeLayer("strategy_feature_inject", feature_inject_overrides, "<strategy:feature_inject>", "strategy.feature_inject"),
        )
    layers.extend([
        MergeLayer("strategy_accel", accel_layer, "<wings-accel>", "strategy.accel"),
        MergeLayer("user_cli", user_layer, "<user_cli>", "user_cli"),
    ])
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


def resolve_config(
    env: ResolvedEnv,
    target: Target,
    user_input: UserInput = UserInput(),
    device_count: int | None = None,
    placement: ClusterPlacement | None = None,
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
    7. 组装 ResolvedConfig

    Args:
        env: 已解析环境 —— config_root(已定位真实根)/ hardware / engine_version。
        target: 解析目标 —— model_name / topology(大策略层判定)/ engine。
        user_input: 用户 CLI 意图 —— cli_overrides(已翻译为引擎参数名)/ cli_dropped(审计)/
            feature_switches(驱动小策略层 FeatureOverlay 从 model.yaml ``features`` 块拼特性参数)。
        device_count: 下发卡数(全程规模:并行协调 / 单机 TP 收缩;None=不触发)。
        placement: 分布式集群寻址(multi_node/PD 选 node、判定 head、替换占位符;
            None=单机/无运行时上下文→占位)。

    Returns:
        ``ResolvedConfig``:包含最终 traces、resolution_notes、多机场景信息与审计附加字段。

    Raises:
        NotImplementedError: topology 为 PD 分离(pd_prefill/pd_decode)时(往后做)。
        ValueError: multi_node 选 node 强校验失败 / DP 协调越界(详见 strategy.topology_inject)。
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
    # STANDALONE 全流程;MULTI_NODE 走 per-node 加载(+ 有运行时上下文则选 node 注入);
    # PD 分离仍未实现(明确往后做)。
    if topology not in (Topology.STANDALONE, Topology.MULTI_NODE):
        raise NotImplementedError(
            f"Topology '{topology.value}' not yet implemented. "
            "Only 'standalone' and 'multi_node' are supported; PD disaggregation is deferred."
        )

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

    # 特性覆盖层:按开关从 model.yaml 顶层 `features` 块拼特性参数。
    # features 是模型级(yaml 顶层),对 standalone / multi_node 各节点统一应用;算一次复用。
    # 无 model recipe(fallback)/ 无 features 块 / 无开关 → feature_overrides 为空(no-op)。
    feature_overrides, feature_notes = feature_overlay_transform(
        {},
        {
            "features": (model_data or {}).get("features"),
            "feature_switches": feature_switches or {},
        },
    )

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
        scenario = _select_scenario(
            model_data, topology, pod_count=(len(node_ips) if node_ips else None)
        )
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
                scenario_engine_config, strategy_overrides, feature_overrides,
                accel_layer, user_layer,
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
                    MergeLayer("strategy_feature_env", strategy_env_layer, "<strategy:feature_env_inject>", "strategy.feature_env_inject"),
                )
            env_traces = trace_merge(env_layers)

            # system_setup 构建(仅场景层,从空集合起)
            system_setup = _build_system_setup(
                scenario["system_setup"],
                str(model_path),
                scenario["system_setup_source_prefix"],
            )

    # ── 5. 组装结果:source_files + resolution_notes(查找/合并轨迹)+ ResolvedConfig ──
    # 仅将实际存在的文件加入 source_files
    source_files: List[str] = []
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
        resolution_notes["resolved_version_dir"] = (
            str(config_root / "engines" / engine / f"v{engine_version.resolved}")
        )
        resolution_notes["version_is_fallback"] = "true" if engine_version.is_fallback else "false"
        resolution_notes["requested_version"] = engine_version.requested or "<none>"
        resolution_notes["resolved_version"] = engine_version.resolved

    # 查找轨迹 — 模型匹配结果
    resolution_notes["matched_model_yaml"] = str(model_path) if model_path is not None else platform_path_str
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
    resolution_notes.update(feature_notes)  # 特性附加/跳过摘要(feature_overlay)
    resolution_notes.update(feature_inject_notes)  # SmartQoS/EnableTrace/Metrics 注入摘要
    resolution_notes["min_engine_version"] = min_engine_check["min_engine_version"]
    resolution_notes["engine_version_for_min_check"] = min_engine_check["engine_version_for_min_check"]
    resolution_notes["engine_version_for_min_check_source"] = min_check_version_source
    resolution_notes["min_engine_version_check"] = min_engine_check["min_engine_version_check"]
    resolution_notes["min_engine_version_check_reason"] = min_engine_check[
        "min_engine_version_check_reason"
    ]
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
