"""multi_node 自定义传参(--config-file)的 per-node 派生策略层。

与 recipe 路径(``strategy/topology_inject``)不同:custom 跳过 recipe 后**无模板 TP/DP**,
推理不依赖 yaml。本层按 engine × 节点身份**主动派生** §5.1.3 那批 per-node 参数/ENV
(``nnodes``/``node_rank``/``master_addr``/``headless`` + DP 通信参数 + 网卡/IP env),
即使 config-file 完全没有也要补出来(用户可能删光了派生行)。

范式对齐 ``feature_inject``:注册表 + 引擎分派 + skip 兜底。新增引擎只在注册表加条目,
主体 ``multinode_custom_derive`` 不随引擎增长而改。

派生规则($4.4 custom 专属,不与 recipe 的 detect_layout/coordinate_parallelism 混用):
- layout 由 ``TP vs device_count`` 推断:``tp > device_count`` → TP_across,否则 DP_across。
  缺 device_count 时报错阻断(派生身份键强依赖 device_count)。
- 全局 DP 缺省:未填 ``data_parallel_size`` 时默认 DP=1。
- ``node_rank``/``headless``/``master_addr``/``nnodes`` 两引擎通用派生;
  vllm-ascend 额外 DP 通信参数(data_parallel_size_local/start_rank/address);
  sglang 派生 ``dist_init_addr``(host=master_ip 框架派生,port 用户可填、缺省 5000,
  见 SGLANG_DIST_PORT;dist_init_addr 不在黑名单,§5.1.3 端口用户可填);
  mindie 本阶段 skip(留 notes)。

本模块返回纯数据(override / env / system_setup commands / notes),不写文件。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, NamedTuple, Optional

from wings_ctl.strategy.parallelism import dp_local_from_device_count, dp_start_rank
from wings_ctl.strategy.topology_inject import select_node

logger = logging.getLogger(__name__)

# 网卡解析对齐 15ffcc6 架构:custom 路径的 env 声明 ``$IFACE_NAME`` 占位,
# 由 config_resolver 的 post_merge.apply_network_env_strategy 在 Python 侧按本 Pod IP
# 解析真实网卡并覆盖(script_builder 已不再 inline 执行 system_setup.commands)。


# 布局标签(与 topology_inject 概念一致,但 custom 的推断规则不同——见 _compute_layout)。
LAYOUT_DP_ACROSS = "DP_across"
LAYOUT_TP_ACROSS = "TP_across"
LAYOUT_NONE = "NONE"  # 默认 DP=1(无跨 Pod DP):仅派生公共身份键,不派生 DP 通信参数

# sglang --dist-init-addr 端口缺省值(5000,用户拍板)。dist_init_addr 不在黑名单,
# **端口用户可填**(设计 §5.1.3);框架只派生 host(master IP),合并用户 port:
# dist_init_addr = "<master_ip>:<port>"。用户未填端口时用此缺省值。
SGLANG_DIST_PORT = 5000


class MultinodeCtx(NamedTuple):
    """multi_node custom 派生所需运行时上下文(纯数据)。"""

    engine: str
    device_count: Optional[int]
    rank_ip: str
    node_ips: List[str]
    master_ip: Optional[str]


class MultinodeDerive(NamedTuple):
    """派生结果:params 覆盖层 / env 覆盖层 / system_setup 命令 / notes。"""

    engine_config: Dict[str, Any]
    env: Dict[str, str]
    system_setup_commands: List[str]
    notes: Dict[str, str]


# 引擎级派生登记。仅登记"本阶段可派生"的引擎;mindie 不登记 → skip。
# key = engine, value = 派生函数
#   (ctx, sel, cfg) -> params_dict
#   ctx: MultinodeCtx(运行时上下文);sel: select_node 结果(角色/index);
#   cfg: config-file 已归一 snake params(用户 TP/DP/端口 等,deriver 自行提取)。
_REGISTRY: Dict[str, Any] = {}


def _register(engine: str):
    """装饰器:注册某引擎的 params 派生器。"""

    def deco(fn):
        _REGISTRY[engine] = fn
        return fn

    return deco


def _resolve_node_ctx(ctx: MultinodeCtx) -> NamedTuple:
    """选本 Pod 节点身份(复用 select_node 纯函数,含强校验)。

    Raises:
        ValueError: 运行时 IP 信息不合法 / 与 NODE_IPS 规模不一致(透传自 select_node)。
    """
    return select_node(
        len(ctx.node_ips),
        rank_ip=ctx.rank_ip,
        node_ips=ctx.node_ips,
        master_ip=ctx.master_ip,
    )


def _compute_layout(tp: int, device_count: int, dp: int) -> str:
    """按 TP vs device_count 推断布局($4.4)。

    - ``tp > device_count`` → TP_across(一个 TP 组跨多 Pod)。
    - 用户显式配 ``dp > 1`` → DP_across(DP 跨 Pod)。
    - 其余(tp ≤ device_count 且 dp ≤ 1,即默认 DP=1)→ 无跨 Pod DP,**NONE**(不派生 DP 通信参数)。
    """
    if tp > device_count:
        return LAYOUT_TP_ACROSS
    if dp > 1:
        return LAYOUT_DP_ACROSS
    return LAYOUT_NONE  # 默认 DP=1:无跨 Pod DP,不派生 size_local/start_rank/address


def _derive_common(ctx: MultinodeCtx, sel) -> Dict[str, Any]:
    """两引擎通用 per-node 参数:nnodes/node_rank/master_addr + worker headless。"""
    out: Dict[str, Any] = {
        "nnodes": len(ctx.node_ips),
        "node_rank": sel.index,
    }
    if ctx.master_ip is not None:
        out["master_addr"] = ctx.master_ip
    # worker(非 head)才加 headless;head 不加(index 0 == master)。
    if sel.role == "worker":
        out["headless"] = True
    return out


def _derive_dp(ctx: MultinodeCtx, sel, device_count: int, tp: int, dp: int) -> Dict[str, Any]:
    """vllm-ascend DP 通信参数:data_parallel_size_local/start_rank/address。

    DP_across:TP 在单 Pod 内,DP 跨 Pod。dp_local = device_count // tp。
    """
    dp_local = dp_local_from_device_count(device_count, tp)
    start_rank = dp_start_rank(sel.index, dp_local)
    return {
        "data_parallel_size_local": dp_local,
        "data_parallel_start_rank": start_rank,
        # DP 通信的 master 地址(head IP),各节点一致(recipe: head/worker 均 $HEAD_IP)。
        # $5.1.3 归框架派生(用户填不出,黑名单内 data_parallel_address)。
        "data_parallel_address": ctx.master_ip or ctx.node_ips[0],
    }


def _derive_env_common(ctx: MultinodeCtx) -> Dict[str, str]:
    """两引擎通用网卡/IP env:本 Pod 用真实 rank_ip 与运行时探测网卡。"""
    return {
        # IP 类:调度后才知道,用户填不出 → 框架派生本 Pod 真实 RANK_IP。
        "HCCL_IF_IP": ctx.rank_ip,
        # 网卡类:默认路由探测 + eth0 兜底;经 system_setup.commands 运行时赋值。
        "GLOO_SOCKET_IFNAME": "$IFACE_NAME",
        "TP_SOCKET_IFNAME": "$IFACE_NAME",
        "HCCL_SOCKET_IFNAME": "$IFACE_NAME",
    }


def _derive_env_vllm_common(ctx: MultinodeCtx) -> Dict[str, str]:
    """nvidia vllm 网卡 env(nvidia 无 HCCL_IF_IP,用 NCCL)。"""
    return {
        "GLOO_SOCKET_IFNAME": "$IFACE_NAME",
        "NCCL_SOCKET_IFNAME": "$IFACE_NAME",
    }


def _extract_dist_port(dist_init_addr: Optional[Any]) -> int:
    """从用户 config-file 的 ``dist_init_addr`` 提取端口,sglang 用。

    仅取端口部分(框架派生 host,覆盖用户 host);未填/无端口 → 缺省 SGLANG_DIST_PORT。
    支持 ``host`` / ``host:port`` 两种形态。端口非 1-65535 时按缺省处理(不阻断,
    用户对参数负责,框架只取能用的端口)。

    Returns:
        int 端口。
    """
    if not dist_init_addr:
        return SGLANG_DIST_PORT
    text = str(dist_init_addr).strip()
    # 形如 host:port(最后一段 rsplit 冒号取端口);无冒号则视为纯 host → 缺省端口。
    if ":" not in text:
        return SGLANG_DIST_PORT
    maybe_port = text.rsplit(":", 1)[-1]
    try:
        port = int(maybe_port)
    except (TypeError, ValueError):
        return SGLANG_DIST_PORT
    if not 1 <= port <= 65535:
        return SGLANG_DIST_PORT
    return port


@_register("vllm")
def _derive_vllm(ctx: MultinodeCtx, sel, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """vllm(nvidia):公共四件套 + DP_across 时的 DP 通信参数。

    nvidia 同样注册 --data-parallel-size-local/-start-rank/-address(arg_utils:1012-1025);
    用户显式配全局 DP(data_parallel_size>1)→ DP_across → 框架派生 size_local/start_rank/address,
    与 vllm-ascend 派生逻辑一致。nvidia 场景少用 DP,但用户一旦配 DP,语义同 ascend。
    """
    device_count = ctx.device_count
    dp = cfg.get("data_parallel_size") or 1
    tp = cfg.get("tensor_parallel_size") or 1
    out = _derive_common(ctx, sel)
    if device_count is not None and _compute_layout(tp, device_count, dp) == LAYOUT_DP_ACROSS:
        out.update(_derive_dp(ctx, sel, device_count, tp, dp))
    return out


@_register("vllm-ascend")
def _derive_vllm_ascend(ctx: MultinodeCtx, sel, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """vllm-ascend:公共四件套 + DP_across 的 DP 通信参数(逻辑同 vllm)。"""
    device_count = ctx.device_count
    dp = cfg.get("data_parallel_size") or 1
    tp = cfg.get("tensor_parallel_size") or 1
    out = _derive_common(ctx, sel)
    if device_count is not None and _compute_layout(tp, device_count, dp) == LAYOUT_DP_ACROSS:
        out.update(_derive_dp(ctx, sel, device_count, tp, dp))
    return out


@_register("sglang")
def _derive_sglang(ctx: MultinodeCtx, sel, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """sglang:公共身份键(nnodes/node_rank,无 master_addr/headless)+ dist_init_addr。

    sglang 集群寻址用 ``--dist-init-addr``(=--nccl-init-addr),非 vllm 的 master_addr。
    - host 框架派生(master IP,各节点一致,用户填不出);
    - port 用户可填(设计 §5.1.3):从 config-file ``dist_init_addr`` 提取,未填缺省 5000;
    - 无 headless、无 DP 通信参数(sglang 无 --data-parallel-size-local/-start-rank/-address)。
    公共身份键经 _derive_common 派生,但其会带出 master_addr/headless——对 sglang 而言
    master_addr 是 vllm 专用(master-addr 不存在),故此处手动取 nnodes/node_rank,丢弃 master_addr。
    """
    out: Dict[str, Any] = {
        "nnodes": len(ctx.node_ips),
        "node_rank": sel.index,
    }
    master_ip = ctx.master_ip or ctx.node_ips[0]
    port = _extract_dist_port(cfg.get("dist_init_addr"))
    out["dist_init_addr"] = f"{master_ip}:{port}"
    return out


def _check_custom_parallelism_consistency(
    engine_config: Dict[str, Any], *, device_count: int
) -> None:
    """$4.4 框架只校验「派生所需」:缺 device_count → 阻断;dp_local ≤ DP 校验。

    Args:
        engine_config: 当前 engine_config(含用户可能填的 TP/DP)。
        device_count: 下发卡数;None → 报错(派生身份键强依赖 device_count)。

    Raises:
        ValueError: 缺 device_count / dp_local > 全局 DP。
    """
    if device_count is None:
        raise ValueError(
            "multi_node custom parameter derivation requires --device-count; it is currently missing. "
            "Provide --device-count for the current Pod to derive per-node parameters."
        )
    dp = engine_config.get("data_parallel_size") or 1
    dp_local = engine_config.get("data_parallel_size_local")
    if dp_local is not None and dp_local > dp:
        raise ValueError(
            f"Custom parameter parallelism validation failed: data_parallel_size_local={dp_local} "
            f"> data_parallel_size={dp}; dp_local must not exceed global DP."
        )


def multinode_custom_derive(
    engine: str,
    ctx: MultinodeCtx,
    *,
    config_file_engine_config: Optional[Dict[str, Any]] = None,
) -> MultinodeDerive:
    """multi_node custom 派生入口:按 engine 派生 per-node params/env 与 system_setup。

    与 ``feature_inject_transform`` 同构:注册表 + 引擎分派 + skip 兜底。不支持的引擎
    (mindie)只记 notes["...skip"] 优雅降级,不崩溃。

    Args:
        engine: 引擎名(注册表分发依据)。
        ctx: 运行时上下文(IP/节点/device_count)。
        config_file_engine_config: config-file 已归一 params(用户填的 TP/DP/端口 等用于
            布局/一致性/派生),可缺省;缺省时按 DP=1、TP 未知(=1)推断。

    Returns:
        MultinodeDerive(engine_config, env, system_setup_commands, notes)。
    """
    cfg = config_file_engine_config or {}
    deriver = _REGISTRY.get(engine)
    if deriver is None:
        return MultinodeDerive(
            engine_config={},
            env={},
            system_setup_commands=[],
            notes={
                # 引擎未登记 → 不派生,但 custom 多节点恒已注入(config_resolver.py
                # resolve_custom_config 无占位分支),故仍标 "injected" 让 startup_log
                # 角色摘要 elif 守卫走进;skip 原因由下方 multinode_custom.skip 承载。
                "multi_node_injection_status": "injected",
                "multinode_custom.skip": f"engine={engine} not supported",
            },
        )

    # 派生所需一致性校验(先于选节点;缺 device_count 直接阻断)。
    # device_count 是 MaaS 第 2 页必填的启动引导参数,multi_node 下所有引擎恒有值;
    # dp_local≤DP 校验对 sglang 惰性无害(不派生 size_local → 恒 None 不触发)。
    _check_custom_parallelism_consistency(cfg, device_count=ctx.device_count)
    sel = _resolve_node_ctx(ctx)
    dp = cfg.get("data_parallel_size") or 1
    tp = cfg.get("tensor_parallel_size") or 1
    params = deriver(ctx, sel, cfg)

    # env:IP + 网卡类($5.1.5);nvidia 与 ascend 网卡/身份 env 键不同。
    # sglang 同 nvidia 型网卡 env(GLOO/NCCL,无 HCCL_IF_IP),走 _derive_env_vllm_common。
    env = _derive_env_common(ctx) if engine in ("vllm-ascend",) else _derive_env_vllm_common(ctx)
    # system_setup:不再注入 NIC 探测 shell 命令(15ffcc6 起 script_builder 不再
    # inline 执行 commands);网卡由 apply_network_env_strategy 在 Python 侧解析覆盖。
    system_setup_commands: List[str] = []

    notes: Dict[str, str] = {
        # canonical 键:与 recipe 路径(config_resolver.py multi_node_* notes)对齐,
        # 供 script_builder._build_analyzer_preamble 的 worker 跳过判定读 multi_node_index、
        # startup_log 角色摘要读 multi_node_role/multi_node_index/multi_node_pod_count、
        # startup_log elif 守卫读 multi_node_injection_status。custom 路径无占位分支
        # (config_resolver.py resolve_custom_config 恒 nodes=None),故恒 "injected"。
        "multi_node_role": sel.role,
        "multi_node_index": str(sel.index),
        "multi_node_pod_count": str(len(ctx.node_ips)),
        "multi_node_injection_status": "injected",
        # multinode_custom 诊断键:deriver 日志行 + layout 测试用,保留不删。
        "multinode_custom.engine": engine,
        "multinode_custom.role": sel.role,
        "multinode_custom.index": str(sel.index),
        "multinode_custom.pod_count": str(len(ctx.node_ips)),
        "multinode_custom.layout": _compute_layout(tp, ctx.device_count, dp),
        "multinode_custom.tp": str(tp),
        "multinode_custom.dp": str(dp),
    }
    logger.info(
        "multi_node custom derivation: engine=%s role=%s index=%d pod_count=%d params=%s",
        engine, sel.role, sel.index, len(ctx.node_ips), sorted(params),
    )
    return MultinodeDerive(
        engine_config=params,
        env=env,
        system_setup_commands=system_setup_commands,
        notes=notes,
    )
