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

import functools
import logging
from typing import Any, Dict, List, NamedTuple, Optional

from wings_ctl.strategy.parallelism import dp_start_rank
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
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        _REGISTRY[engine] = fn
        return wrapper

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


# 这些 DP 模式要求"每 Pod/rank 提供 API endpoint"(本地 worker 自行起服务进程,
# 由 LB / connector / rank 各自对外),而非由 master 远程调起的纯计算节点。
# 其中 Hybrid 与 headless 直接被 vLLM ``arg_utils``
# 互斥断言(``not headless or not data_parallel_hybrid_lb``);
# external / multi-port 则因"每 Pod 须保留对外 API 端点"而不应 headless。
# 因此多节点派生层在遇到这类 DP 模式时**不注入 headless**,避免与用户显式声明的
# hybrid / external / multi-port external 参数并置导致引擎启动失败。
_PER_NODE_API_DP_FLAGS = (
    "data_parallel_hybrid_lb",
    "data_parallel_external_lb",
    "data_parallel_multi_port_external_lb",
)


def _dp_serves_per_node_api(cfg: Dict[str, Any]) -> bool:
    """判断自定义传参的 DP 模式是否要求"每 Pod/rank 提供 API endpoint"。

    仅当用户显式声明了 hybrid / external / multi-port external 任一标志时为真——
    这类模式 worker 各自不 headless(见 _PER_NODE_API_DP_FLAGS 上方的成因注释:
    其中 Hybrid 与 headless 被 vLLM ``arg_utils`` 直接互斥断言;external / multi-port
    则是"每 Pod 须保留对外 API endpoint"的语义要求)。

    Args:
        cfg: config-file 已归一 snake params(用户 TP/DP/hybrid/external 等标志)。

    Returns:
        True → 该 DP 模式每节点/rank 提供 API,派生层**不注入 headless**;
        False → 内部 DP / 普通 worker(每 Pod 内多 rank 由 master 调起),仍需 headless。
    """
    return any(cfg.get(k) for k in _PER_NODE_API_DP_FLAGS)


def _derive_common(ctx: MultinodeCtx, sel, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """两引擎通用 per-node 参数:nnodes/node_rank/master_addr + worker headless。

    Args:
        cfg: config-file 已归一 snake params,用于判断 DP 模式(hybrid/external/multi-port
            external 等"每节点提供 API"的布局在 worker 上不注入 headless,见 _dp_serves_per_node_api)。
    """
    out: Dict[str, Any] = {
        "nnodes": len(ctx.node_ips),
        "node_rank": sel.index,
    }
    if ctx.master_ip is not None:
        out["master_addr"] = ctx.master_ip
    # worker(非 head)才加 headless;head 不加(index 0 == master)。
    # Hybrid / external / multi-port external DP 模式下 worker 各自提供 API endpoint,
    # 故不注入 headless。内部 DP(未声明上述标志)的 worker 仍是纯计算节点,需 headless。
    if sel.role == "worker" and not _dp_serves_per_node_api(cfg):
        out["headless"] = True
    return out


def _is_external_dp(cfg: Dict[str, Any]) -> bool:
    """仅判断用户显式声明的 pure-external DP(``data_parallel_external_lb``)。

    与 ``_dp_serves_per_node_api``(三者都管 headless)不同,这里只看 external:
    只有它会被 vLLM serve.py 用 ``data_parallel_start_rank is not None`` 误判为
    hybrid 而撞车(``is_external_lb and is_hybrid_lb`` → 启动被拒),故需去掉 start_rank。
    hybrid / multi-port external 自身带显式标志,serve.py 各自归位,不因 start_rank
    撞车,保留 start_rank(仍作 DP 通信 rank 来源)。
    """
    return bool(cfg.get("data_parallel_external_lb"))


def _derive_dp(ctx: MultinodeCtx, sel, size_local: int, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """vllm DP 通信参数:data_parallel_start_rank/address(纯 internal/hybrid 路径)。

    DP_across:TP 在单 Pod 内,DP 跨 Pod。``data_parallel_size_local`` **由用户填写**
    (custom 用户自管,不在黑名单);这里只派生框架权威的 start_rank 与 address:
    start_rank = 本 Pod index × 用户 size_local。

    例外: **pure-external**(用户声明 ``data_parallel_external_lb``)时**不派生**
    ``data_parallel_start_rank``——vLLM serve.py 会把 start_rank 识别为 hybrid,
    与 external 撞成"多种 LB 模式"而拒绝启动。external 每 Pod 独立对外、DP 组由
    vLLM 按节点自推断 rank。

    external(外部负载均衡)要求每条 rank 各带独立对外 API 端点、由外部 LoadBalancer
    统一分发,因此 **``data_parallel_size_local`` 必须为 1**;>1 时 vLLM 会拒绝启动。
    要让 ``data_parallel_external_lb + data_parallel_size_local>1`` 成立,必须做
    **per-rank 进程展开**(每个 Pod 展开成 size_local 个独立进程、各自 rank/端口/端点),
    而普通 custom 是"每 Pod 单进程"模型,不做该展开——**per-rank 展开已由 PD 场景实现
    (``_pd_process_derive_vllm``),普通 custom 不建议重复实现**。故此处对 external 仅
    透传(保 address、去 start_rank);用户显式声明 external 时打一条**告警日志**
    提醒该约束、并引导 size_local>1 的诉求走 PD 布局。不硬报错以免破坏存量 external 用户。
    """
    out: Dict[str, Any] = {}
    if not _is_external_dp(cfg):
        out["data_parallel_start_rank"] = dp_start_rank(sel.index, size_local)
    else:
        # external 要求 data_parallel_size_local==1;>1 需 per-rank 进程展开,该展开已由
        # PD 实现(_pd_process_derive_vllm),普通 custom 单进程模型不重复实现。故此处
        # 不校验用户填的 size_local、只外传 external 时吐一条用户告警说明该约束。
        # 每个 Pod 进程内 _derive_dp 仅调一次,告警不重复。
        logger.warning(
            "data_parallel_external_lb (external load balancer) requires "
            "data_parallel_size_local==1, otherwise vLLM will refuse to start. "
            "For data_parallel_external_lb with data_parallel_size_local>1, "
            "prefer the PD (parallel deployment) separation mode."
        )
    # DP 协调的 master 地址(head IP),各节点一致(recipe: head/worker 均 $HEAD_IP)。
    # external 亦需该地址(DP>1 时 Coordinator 用它建 ZMQ,见 vLLM coordinator.py)。
    # $5.1.3 归框架派生(用户填不出,黑名单内 data_parallel_address)。
    out["data_parallel_address"] = ctx.master_ip or ctx.node_ips[0]
    return out


def _require_user_size_local(cfg: Dict[str, Any], engine: str) -> int:
    """DP_across 下取用户填写的 data_parallel_size_local;未填 → 阻断。

    设计:custom multi_node 的 ``data_parallel_size_local`` 用户能填出来(每 Pod 分配的
    local DP 副本数),故不再由框架按 ``device_count // tp`` 自动派生,**完全要求用户填写**。
    DP_across(用户配全局 DP>1)为跨 Pod DP 布局,size_local 是派生 start_rank 的前置;
    缺失则无法展开,直接报错并提示用户填写。

    Args:
        cfg: config-file 已归一 snake params。
        engine: 引擎名,用于报错文案。

    Returns:
        用户填写的正整数 data_parallel_size_local。

    Raises:
        ValueError: DP_across 未填写 data_parallel_size_local 或值非法。
    """
    raw = cfg.get("data_parallel_size_local")
    if raw is None:
        raise ValueError(
            f"multi_node {engine} DP_across layout requires data_parallel_size_local "
            "(local DP instances per pod); it is user-managed and must be provided."
        )
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        raise ValueError(f"multi_node {engine} data_parallel_size_local must be a positive integer; got {raw!r}.")
    return raw


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


# 引擎 → 网卡/IP env 派生器的固定数据映射(custom PD 网络 env)。
# 引擎差异收敛为一张查表,而非在 config_resolver 主流程散落 engine 分支:
# 新增引擎只需在此登记对应派生器,主体派生逻辑不随引擎增长而改。
_NETWORK_ENV_DERIVERS: Dict[str, Any] = {
    "vllm": _derive_env_vllm_common,
    "vllm-ascend": _derive_env_common,
}


def derive_common_network_env(engine: str, ctx: MultinodeCtx) -> Dict[str, str]:
    """按引擎固定的网卡/IP env 映射派生 common 通信 env(custom PD 跨 Pod 与 multi_node 共用)。

    - ``vllm`` → nvidia 型(GLOO/NCCL);
    - ``vllm-ascend`` → ascend 型(HCCL_IF_IP + GLOO/TP/HCCL_SOCKET_IFNAME)。

    仅接受 custom PD 白名单内引擎(_CUSTOM_PD_SUPPORTED_ENGINES);其它引擎(未登记于
    ``_NETWORK_ENV_DERIVERS``)在此明确报错,不静默落入默认分支。
    """
    deriver = _NETWORK_ENV_DERIVERS.get(engine)
    if deriver is None:
        raise ValueError(
            f"derive_common_network_env: unsupported engine {engine!r} "
            f"(expected {sorted(_NETWORK_ENV_DERIVERS)})"
        )
    return deriver(ctx)


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
    out = _derive_common(ctx, sel, cfg)
    if device_count is not None and _compute_layout(tp, device_count, dp) == LAYOUT_DP_ACROSS:
        size_local = _require_user_size_local(cfg, "vllm")
        out.update(_derive_dp(ctx, sel, size_local, cfg))
    return out


@_register("vllm-ascend")
def _derive_vllm_ascend(ctx: MultinodeCtx, sel, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """vllm-ascend:公共四件套 + DP_across 的 DP 通信参数(逻辑同 vllm)。"""
    device_count = ctx.device_count
    dp = cfg.get("data_parallel_size") or 1
    tp = cfg.get("tensor_parallel_size") or 1
    out = _derive_common(ctx, sel, cfg)
    if device_count is not None and _compute_layout(tp, device_count, dp) == LAYOUT_DP_ACROSS:
        size_local = _require_user_size_local(cfg, "vllm-ascend")
        out.update(_derive_dp(ctx, sel, size_local, cfg))
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


def _check_custom_parallelism_consistency(engine_config: Dict[str, Any], *, device_count: int) -> None:
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
