"""E2E test — 自定义传参方式(--config-file)multi_node(阶段 2)。

覆盖(§5.1.5 strategy_multinode_custom 派生层):
(a) vllm MULTI_NODE + placement → 派生 nnodes/node_rank/master_addr + worker headless,
    进 engine_config_traces(strategy_multinode_custom 层),argv 渲染。
(b) vllm-ascend DP_across → 派生 data_parallel_size_local/start_rank/address。
(c) data_parallel_rpc_port 用户可填优先级 vs 缺省(未填)。
(d) env:ascend 派生 HCCL_IF_IP=rank_ip;*_SOCKET_IFNAME 渲染为 "$IFACE_NAME"运行时形式;
    system_setup.commands 含 NIC 探测。
(e) sglang 派生 nnodes/node_rank/dist_init_addr(host=master_ip,port 用户可填/缺省 5000)。
(f) vllm 系缺 device_count → ValueError(派生身份键强依赖 device_count;sglang 不需)。
(g) 端到端 vllm:build_scripts 产物含 env export + inline NIC 探测 + argv。
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

import pytest

from wings_ctl.core.config_resolver import resolve_custom_config
from wings_ctl.core.models import (
    ClusterPlacement,
    CustomConfigFile,
    ResolvedEnv,
    Target,
    UserInput,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.rendering.script_builder import build_scripts
from wings_ctl.strategy.multinode_custom import (
    MultinodeCtx,
    multinode_custom_derive,
)

CLI_OVERRIDES = {"model": "/weights/MiniMax-M3-MXFP8", "served_model_name": "MiniMax-M3-MXFP8"}

# 三节点集群(含 master 即 head);本 Pod 为 worker(rank_ip=第三节点)。
PLACEMENT_WORKER = ClusterPlacement(
    rank_ip="10.0.0.3",
    node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"],
    master_ip="10.0.0.1",
)
# 本 Pod 为 head(rank_ip == master_ip)。
PLACEMENT_HEAD = ClusterPlacement(
    rank_ip="10.0.0.1",
    node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"],
    master_ip="10.0.0.1",
)

CONFIG_FILE_VLLM = CustomConfigFile(
    params={
        "max_num_seqs": 256,
        "tensor_parallel_size": 2,
        # 用户可填 rpc_port(不在黑名单)→ 应保留(report c)。
        "data_parallel_rpc_port": 13389,
    },
    env={},
)


def _env(config_root: Path, hardware_info_path: Path, engine: str) -> ResolvedEnv:
    os.environ["ENGINE_VERSION"] = "0.19.0"
    try:
        hardware = resolve_hardware(hardware_info_path)
        engine_version = resolve_engine_version(
            config_root, hardware.hardware_family, engine=engine
        )
        return ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=engine_version)
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def _resolve(config_root: Path, hardware_info_path: Path, *, engine="vllm",
             config_file=CONFIG_FILE_VLLM, placement=PLACEMENT_WORKER,
             device_count: int | None = 2, user_input=None):
    user_input = user_input or UserInput(cli_overrides=CLI_OVERRIDES)
    return resolve_custom_config(
        _env(config_root, hardware_info_path, engine),
        Target(model_name="MiniMax-M3-MXFP8", topology=Topology.MULTI_NODE, engine=engine),
        config_file=config_file,
        user_input=user_input,
        device_count=device_count,
        placement=placement,
    )


# ─── (a) vllm worker:派生公共四件套 ───


def test_a_vllm_worker_derives_common(config_root, hardware_info_path):
    resolved = _resolve(config_root, hardware_info_path)
    tr = resolved.engine_config_traces
    # nnodes = len(NODE_IPS)
    assert tr["nnodes"].final_value == 3
    assert tr["nnodes"].final_layer == "strategy_multinode_custom"
    # node_rank = 本 Pod index(worker → 3rd node → 2)
    assert tr["node_rank"].final_value == 2
    # master_addr = NODE_IPS[0] = master_ip
    assert tr["master_addr"].final_value == "10.0.0.1"
    # worker → headless
    assert tr["headless"].final_value is True
    # 用户填的 rpc_port 保留(config_file 层,不在派生集)
    assert tr["data_parallel_rpc_port"].final_value == 13389
    assert tr["data_parallel_rpc_port"].final_layer == "config_file"

    argv = build_argv(resolved.engine_config_traces, engine="vllm")
    joined = shlex.join(argv)
    assert "--nnodes 3" in joined
    assert "--node-rank 2" in joined
    assert "--master-addr 10.0.0.1" in joined
    assert "--headless" in joined
    assert "--data-parallel-rpc-port 13389" in joined


def test_a2_vllm_head_no_headless(config_root, hardware_info_path):
    resolved = _resolve(config_root, hardware_info_path, placement=PLACEMENT_HEAD)
    tr = resolved.engine_config_traces
    assert tr["node_rank"].final_value == 0
    # head 无 headless
    assert "headless" not in tr
    argv = shlex.join(build_argv(resolved.engine_config_traces, engine="vllm"))
    assert "--headless" not in argv


# ─── (b) vllm-ascend DP_across:派生 DP 通信参数(单测,无 ascend 资产)───


def test_b_ascend_derives_dp(config_root, hardware_info_path):
    ctx = MultinodeCtx(
        engine="vllm-ascend",
        device_count=8,
        rank_ip="10.0.0.3",
        node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"],
        master_ip="10.0.0.1",
    )
    # 用户显式配全局 DP=2 → DP_across;TP 未填 → 1;device_count=8, tp=1 → dp_local=8
    derive = multinode_custom_derive(
        "vllm-ascend", ctx, config_file_engine_config={"data_parallel_size": 2}
    )
    ec = derive.engine_config
    assert ec["nnodes"] == 3
    assert ec["node_rank"] == 2
    assert ec["master_addr"] == "10.0.0.1"
    assert ec["headless"] is True
    # DP_across:dp_local = 8//1 = 8;start_rank = index*8 = 16;address=master_ip
    assert ec["data_parallel_size_local"] == 8
    assert ec["data_parallel_start_rank"] == 16
    assert ec["data_parallel_address"] == "10.0.0.1"
    assert derive.notes["multinode_custom.layout"] == "DP_across"


def test_b2_ascend_tp_across_no_dp(config_root, hardware_info_path):
    """TP > device_count → TP_across,不派生 DP 通信参数(仅公共四件套)。"""
    ctx = MultinodeCtx(
        engine="vllm-ascend",
        device_count=4,
        rank_ip="10.0.0.3",
        node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"],
        master_ip="10.0.0.1",
    )
    # TP=8(跨 over device_count=4)→ TP_across
    derive = multinode_custom_derive(
        "vllm-ascend", ctx, config_file_engine_config={"tensor_parallel_size": 8}
    )
    ec = derive.engine_config
    assert derive.notes["multinode_custom.layout"] == "TP_across"
    assert "data_parallel_size_local" not in ec
    assert "data_parallel_start_rank" not in ec
    assert ec["nnodes"] == 3 and ec["node_rank"] == 2


def test_b3_default_dp1_none_layout(config_root, hardware_info_path):
    """默认 DP=1(用户未填 data_parallel_size)→ 布局 NONE,不派生 DP 通信参数。

    仅派生公共身份键(nnodes/node_rank/master_addr/headless);无 DP 跨 Pod 场景,
    size_local/start_rank/address 不产(引擎默认 size_local=1)。
    """
    ctx = MultinodeCtx(
        engine="vllm",
        device_count=8,
        rank_ip="10.0.0.3",
        node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"],
        master_ip="10.0.0.1",
    )
    derive = multinode_custom_derive("vllm", ctx)  # 未填 DP → dp=1
    ec = derive.engine_config
    assert derive.notes["multinode_custom.layout"] == "NONE"
    assert ec["nnodes"] == 3 and ec["node_rank"] == 2 and ec["master_addr"] == "10.0.0.1"
    assert "data_parallel_size_local" not in ec
    assert "data_parallel_start_rank" not in ec
    assert "data_parallel_address" not in ec


# ─── (c) data_parallel_rpc_port:用户可填 vs 缺省 ───


def test_c_rpc_port_user_provided_wins(config_root, hardware_info_path):
    resolved = _resolve(
        config_root, hardware_info_path,
        config_file=CustomConfigFile(params={"data_parallel_rpc_port": 20000}, env={}),
    )
    assert resolved.engine_config_traces["data_parallel_rpc_port"].final_value == 20000


# ─── (d) env 派生:ascend HCCL_IF_IP + *SOCKET_IFNAME 运行时;system_setup ───


def test_d_ascend_env_derived(config_root, hardware_info_path):
    derive = multinode_custom_derive(
        "vllm-ascend",
        MultinodeCtx(
            engine="vllm-ascend", device_count=8, rank_ip="10.0.0.3",
            node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"], master_ip="10.0.0.1",
        ),
    )
    env = derive.env
    assert env["HCCL_IF_IP"] == "10.0.0.3"
    assert env["GLOO_SOCKET_IFNAME"] == "$IFACE_NAME"
    assert env["TP_SOCKET_IFNAME"] == "$IFACE_NAME"
    assert env["HCCL_SOCKET_IFNAME"] == "$IFACE_NAME"
    # system_setup 不再注入 shell 探测命令(15ffcc6:Python 侧解析网卡)
    assert derive.system_setup_commands == []


def test_d2_vllm_env_derived(config_root, hardware_info_path):
    """nvidia vllm 网卡 env 用 NCCL/GLOO,无 HCCL_IF_IP。"""
    derive = multinode_custom_derive(
        "vllm",
        MultinodeCtx(
            engine="vllm", device_count=8, rank_ip="10.0.0.3",
            node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"], master_ip="10.0.0.1",
        ),
    )
    env = derive.env
    assert "HCCL_IF_IP" not in env
    assert env["GLOO_SOCKET_IFNAME"] == "$IFACE_NAME"
    assert env["NCCL_SOCKET_IFNAME"] == "$IFACE_NAME"


# ─── (e) sglang typeof skip ───


def test_e_sglang_derive():
    """sglang 派生:公共身份键 + dist_init_addr;无 master_addr/headless(设计 §5.1.3)。

    - nnodes/node_rank 派生;dist_init_addr = "<master_ip>:<port>"。
    - port 用户可填(从 config-file dist_init_addr 提取),未填缺省 SGLANG_DIST_PORT=5000。
    - host 恒用 master IP(框架派生,覆盖用户写的 host)。
    - env 走 nvidia 型网卡(GLOO/NCCL,无 HCCL_IF_IP)。
    - device_count 必传(与所有引擎一致):缺省时与其他引擎同样阻断。
    """
    from wings_ctl.strategy.multinode_custom import (
        SGLANG_DIST_PORT,
    )

    # 缺省端口:用户未填 dist_init_addr → port=5000,host=master_ip。
    derive = multinode_custom_derive(
        "sglang",
        MultinodeCtx(
            engine="sglang", device_count=8, rank_ip="10.0.0.3",
            node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"], master_ip="10.0.0.1",
        ),
    )
    assert derive.engine_config["nnodes"] == 3
    assert derive.engine_config["node_rank"] == 2  # rank_ip=10.0.0.3 → index 2
    assert derive.engine_config["dist_init_addr"] == f"10.0.0.1:{SGLANG_DIST_PORT}"
    assert "master_addr" not in derive.engine_config
    assert "headless" not in derive.engine_config
    # env:sglang 走 nvidia 型网卡(GLOO/NCCL),无 HCCL_IF_IP。
    assert "GLOO_SOCKET_IFNAME" in derive.env
    assert "NCCL_SOCKET_IFNAME" in derive.env
    assert "HCCL_IF_IP" not in derive.env
    assert "multinode_custom.skip" not in derive.notes

    # 用户填端口:dist_init_addr="10.0.0.99:29999" → host 被框架覆盖为 master_ip,port 保留。
    derive2 = multinode_custom_derive(
        "sglang",
        MultinodeCtx(
            engine="sglang", device_count=8, rank_ip="10.0.0.3",
            node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"], master_ip="10.0.0.1",
        ),
        config_file_engine_config={"dist_init_addr": "10.0.0.99:29999"},
    )
    assert derive2.engine_config["dist_init_addr"] == "10.0.0.1:29999"

    # sglang 缺 device_count 同样阻断(与 vllm 系一致,device_count 为必传启动参数)。
    with pytest.raises(ValueError, match="device-count"):
        multinode_custom_derive(
            "sglang",
            MultinodeCtx(
                engine="sglang", device_count=None, rank_ip="10.0.0.3",
                node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"], master_ip="10.0.0.1",
            ),
        )


def test_e_sglang_dist_port_extraction():
    """_extract_dist_port:host-only→缺省 / host:port→取 port / 非法 port→缺省 / 空→缺省。"""
    from wings_ctl.strategy.multinode_custom import (
        SGLANG_DIST_PORT,
        _extract_dist_port,
    )

    assert _extract_dist_port(None) == SGLANG_DIST_PORT
    assert _extract_dist_port("") == SGLANG_DIST_PORT
    assert _extract_dist_port("10.0.0.1") == SGLANG_DIST_PORT  # 纯 host → 缺省端口
    assert _extract_dist_port("10.0.0.1:29999") == 29999
    assert _extract_dist_port("10.0.0.1:0") == SGLANG_DIST_PORT  # port 越界 → 缺省
    assert _extract_dist_port("10.0.0.1:70000") == SGLANG_DIST_PORT  # port 越界 → 缺省
    assert _extract_dist_port("10.0.0.1:abc") == SGLANG_DIST_PORT  # 非数字 → 缺省


# ─── (e2) 前端模板占位符 <autofill:...> 不泄漏(config-file 渲染前被 drop / 覆盖)───
# 阶段 3 模板把派生参数以 <autofill:...> 占位符直接放进 params/env(§1 custom-json-template.md)。
# 锁死安全承诺:占位符字面量**不会真正进引擎**——黑名单键被 _filter_config_file_blacklist 静默弃置,
# dist_init_addr(非黑名单)被 strategy_multinode_custom 派生层整键覆盖。


def test_e2_vllm_placeholder_dropped(config_root, hardware_info_path):
    """vllm:master_addr/nnodes/node_rank/headless/DP 通信参数带 <autofill:...> 占位符
    → 全部被黑名单弃置(不入 traces,不渲染进 argv),且正常业务参数保留。"""
    cf = CustomConfigFile(
        params={
            # 派生键(黑名单内)占位符形态 —— 必须被弃,绝不透传
            "master_addr": "<autofill:master_ip>",
            "nnodes": "<autofill:nnodes>",
            "node_rank": "<autofill:node_rank>",
            "headless": "<autofill:headless>",
            "data_parallel_address": "<autofill:data_parallel_address>",
            # 业务参数保持正常
            "max_num_seqs": 256,
            "tensor_parallel_size": 2,
        },
        env={
            "GLOO_SOCKET_IFNAME": "<autofill:iface_name>",
            "NCCL_SOCKET_IFNAME": "<autofill:iface_name>",
        },
    )
    resolved = _resolve(config_root, hardware_info_path, engine="vllm", config_file=cf)
    tr = resolved.engine_config_traces
    # 占位符键在 config_file 层被弃 → 不进 engine_config_traces(黑名单内,drop)。
    # 最终 traces 里的 master_addr/nnodes/node_rank/headless 是**派生层**真实值,不是占位符。
    assert tr["master_addr"].final_value == "10.0.0.1" and "autofill" not in str(tr["master_addr"].final_value)
    assert tr["nnodes"].final_value == 3 and "autofill" not in str(tr["nnodes"].final_value)
    assert tr["node_rank"].final_value == 2
    # 用户填的占位符 headless 被弃;worker 的 headless 由派生层补(True)
    assert tr["headless"].final_value is True
    # DP=1(default/未填)→ NONE 布局 → 不派生 data_parallel_address → 不残留占位符
    assert "autofill" not in str(resolved.engine_config_traces)
    assert "autofill" not in str(resolved.env_traces)
    # audit:占位符键记 dropped
    dropped = {
        d["key"] for d in resolved.config_file_params
        if d["status"] == "dropped"
    }
    for key in ("master_addr", "nnodes", "node_rank", "headless", "data_parallel_address"):
        assert key in dropped
    # env 网卡占位符同样被弃
    assert "GLOO_SOCKET_IFNAME" in dropped and "NCCL_SOCKET_IFNAME" in dropped
    # 业务参数不被误弃
    assert "max_num_seqs" not in dropped and "tensor_parallel_size" not in dropped


def test_e2_sglang_placeholder_covered():
    """sglang:dist_init_addr(非黑名单)带 <autofill:master_ip> host 占位符 + port 缺省 5000
    → 被派生层整键覆盖为 <master_ip>:5000,绝无占位符残留(覆盖在渲染前完成)。

    注意:走 multinode_custom_derive(与既有 sglang 测试同风格,避开 sglang 硬件 recipe 资产)。
    nnodes/node_rank 占位符的黑名单 drop 由公共黑名单的 vllm 测试(test_e2_vllm_placeholder_dropped)
    覆盖——common 黑名单两引擎一致。
    """
    ctx = MultinodeCtx(
        engine="sglang", device_count=8, rank_ip="10.0.0.3",
        node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"], master_ip="10.0.0.1",
    )
    # 模板默认:<autofill:master_ip>:5000 —— host 占位符 + port 缺省 5000
    derive = multinode_custom_derive(
        "sglang", ctx,
        config_file_engine_config={"dist_init_addr": "<autofill:master_ip>:5000"},
    )
    ec = derive.engine_config
    # 被派生层整键覆盖:host=master_ip,port=5000。绝无占位符残留。
    assert ec["dist_init_addr"] == "10.0.0.1:5000"
    assert "autofill" not in str(ec)
    assert derive.engine_config["nnodes"] == 3
    assert derive.engine_config["node_rank"] == 2


# ─── (f) 缺 device_count 阻断 ───


def test_f_missing_device_count_blocks(config_root, hardware_info_path):
    with pytest.raises(ValueError, match="device-count"):
        multinode_custom_derive(
            "vllm",
            MultinodeCtx(
                engine="vllm", device_count=None, rank_ip="10.0.0.3",
                node_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"], master_ip="10.0.0.1",
            ),
        )


# ─── (g) 端到端 vllm:build_scripts 产物含 env export + Python 侧网卡解析 + argv ───


def test_g_vllm_end_to_end_scripts(config_root, hardware_info_path, tmp_path):
    resolved = _resolve(config_root, hardware_info_path)
    # system_setup 结构保留(custom 多节点恒注入),commands 已不再含 shell 探测
    assert resolved.system_setup is not None
    # 网卡/IP 通信变量由 apply_network_env_strategy Python 侧解析覆盖:
    # $IFACE_NAME 占位被替换为本 Pod IP 所属网卡(或 eth0 兜底)。
    iface = resolved.env_traces["GLOO_SOCKET_IFNAME"].final_value
    assert iface != "$IFACE_NAME"

    # 三件产物落盘
    start_path, repro_path = build_scripts(resolved, tmp_path)
    start_text = start_path.read_text(encoding="utf-8")
    # shell 内联探测已移除(15ffcc6 架构:script_builder 不再 inline 执行 commands)
    assert "IFACE_NAME=$(awk" not in start_text
    # env export 写入解析后的真实网卡名(安全值走单引号安全渲染,无 $() 不加双引号)
    assert f"export GLOO_SOCKET_IFNAME={iface}" in start_text
    assert "--nnodes 3" in start_text
    assert "--node-rank 2" in start_text
    # worker(node_rank=2 > 0)不注入 log_analyzer(仅 master 运行分析器)。
    assert "log_analyzer" not in start_text


# ─── (h) canonical 别名归并(§4.4.1):简写/双长名 → canonical 键,不遗漏不透传 ───


def test_h_vllm_short_flags_canonicalized(config_root, hardware_info_path):
    """vllm 简写(:n/-r/-tp/-dp)经 canonical 归并:
    - n→nnodes、r→node_rank 命中黑名单被过滤(不渲染);
    - tp→tensor_parallel_size、dp→data_parallel_size 被派生层 cfg.get 读取。"""
    cf = CustomConfigFile(
        params={
            # 简写(Clippy):n/r 应在黑名单过滤;tp/dp 应被派生层读成 canonical 键。
            "n": 3,
            "r": 1,
            "tp": 2,
            "dp": 4,
        },
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, engine="vllm", config_file=cf)
    tr = resolved.engine_config_traces
    # 简写 n/r → canonical nnodes/node_rank,命中黑名单被弃置(config_file 层不落,
    # 最终由派生层提供);简写 tp/dp → canonical tensor_parallel_size / data_parallel_size
    # (全局 DP 用户自管,非黑名单)→ 进 traces 且派生层读得到。
    assert tr["tensor_parallel_size"].final_value == 2
    assert tr["tensor_parallel_size"].final_layer == "config_file"
    assert tr["data_parallel_size"].final_value == 4
    assert tr["data_parallel_size"].final_layer == "config_file"
    # 黑名单弃置记录:canonical nnodes/node_rank(n/r 归并后)被弃(vllm 框架权威派生),
    # 记 dropped 而不透传;data_parallel_size 用户自管不透传。
    dropped = {d["key"] for d in resolved.config_file_params if d["status"] == "dropped"}
    assert "nnodes" in dropped and "node_rank" in dropped
    assert "data_parallel_size" not in dropped


def test_h1_dp_short_flags_canonicalized(config_root, hardware_info_path):
    """vllm DP 简写 -dpa/-dpp 经 canonical 归并:-dpp(rpc_port 用户可填)透传,
    -dpa(address 黑名单)被弃。"""
    cf = CustomConfigFile(
        params={"dpp": 13389, "dpa": "10.9.9.9"},
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, engine="vllm", config_file=cf)
    tr = resolved.engine_config_traces
    # dpp → data_parallel_rpc_port(用户可填,非黑名单)→ 透传
    assert tr["data_parallel_rpc_port"].final_value == 13389
    assert tr["data_parallel_rpc_port"].final_layer == "config_file"
    # dpa → data_parallel_address(黑名单,框架权威)→ 弃用;dp=1→NONE→不派生→不进 traces
    dropped = {d["key"] for d in resolved.config_file_params if d["status"] == "dropped"}
    assert "data_parallel_address" in dropped
    assert "data_parallel_address" not in tr


def test_h3_sglang_aliases_canonicalized(config_root, hardware_info_path):
    """sglang 双长名 --tp-size/--dp-size 与 --nccl-init-addr 经 canonical 归并:
    tp_size/dp_size → tensor_parallel_size/data_parallel_size(用户自管,留);
    nccl_init_addr → dist_init_addr(**不在黑名单**,端口用户可填,留)。单测黑名单过滤
    (无 sglang 资产)。"""
    from wings_ctl.core.config_resolver import (
        _canonicalize_config_file_params,
        _filter_config_file_blacklist,
    )
    canon = _canonicalize_config_file_params(
        {"tp_size": 8, "dp_size": 2, "nccl_init_addr": "10.0.0.1:29500"},
        engine="sglang",
    )
    assert canon["tensor_parallel_size"] == 8
    assert canon["data_parallel_size"] == 2
    assert canon["dist_init_addr"] == "10.0.0.1:29500"
    kept, dropped = _filter_config_file_blacklist(canon, engine="sglang")
    assert "tensor_parallel_size" in kept and "data_parallel_size" in kept
    # dist_init_addr 现不在黑名单 → 保留(端口用户可填;host 由派生层覆盖)。
    assert "dist_init_addr" in kept
    assert dropped == []


def test_h5_vllm_dp_address_blacklisted(config_root, hardware_info_path):
    """data_parallel_address:框架权威(各节点用 master IP),用户填不出 → vllm/vllm-ascend
    均在黑名单(与 rpc_port 用户可填区分)。

    端到端验 vllm:用户在 config-file 填入 data_parallel_address → 黑名单弃用(记 dropped);
    用户未配全局 DP(dp=1)→ 布局 NONE → 派生层不产 data_parallel_address → 键不进 traces。
    即:用户值不进 config_file 层,无 DP 场景派生层也不补,最终不透传。
    """
    from wings_ctl.core.config_resolver import _config_file_params_blacklist

    # 黑名单:vllm / vllm-ascend 都拦;rpc_port 用户可填不拦。
    for e in ("vllm", "vllm-ascend"):
        assert "data_parallel_address" in _config_file_params_blacklist(e)
    assert "data_parallel_rpc_port" not in _config_file_params_blacklist("vllm")

    # 端到端:用户填 data_parallel_address(未填 data_parallel_size→dp=1→布局 NONE)→
    # 黑名单 dropped,派生层不补(无 DP 场景)→ 不进 traces。
    cf = CustomConfigFile(params={"data_parallel_address": "10.0.0.1"}, env={})
    resolved = _resolve(config_root, hardware_info_path, engine="vllm", config_file=cf)
    dropped = {d["key"] for d in resolved.config_file_params if d["status"] == "dropped"}
    assert "data_parallel_address" in dropped
    assert "data_parallel_address" not in resolved.engine_config_traces


def test_h2_vllm_short_rpc_and_business(config_root, hardware_info_path):
    """简写除黑名单外其余业务键(canonical 归并后仍透传)。"""
    cf = CustomConfigFile(
        params={"data_parallel_rpc_port": 13389, "max_num_seqs": 256},
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, engine="vllm", config_file=cf)
    assert resolved.engine_config_traces["data_parallel_rpc_port"].final_value == 13389


def test_h3_sglang_alias_canonicalized_unit():
    """sglang:--nccl-init-addr 归并到 dist_init_addr;dist_init_addr 不在黑名单 → 保留透传(unit)。"""
    from wings_ctl.core.config_resolver import (
        _canonicalize_config_file_params,
        _config_file_params_blacklist,
    )

    src = _canonicalize_config_file_params(
        {"nccl_init_addr": "10.0.0.1:8000", "tp_size": 8, "dp_size": 4}, engine="sglang"
    )
    assert src == {"dist_init_addr": "10.0.0.1:8000", "tensor_parallel_size": 8, "data_parallel_size": 4}
    # dist_init_addr 不在 sglang 引擎黑名单(端口用户可填)→ 保留透传,不被过滤。
    assert "dist_init_addr" not in _config_file_params_blacklist("sglang")


def test_h4_vllm_short_snake(config_root, hardware_info_path):
    """用户写 kebab/混合形式(docker `data-parallel-size`)→ _to_snake 后归并 canonical。"""
    from wings_ctl.core.config_resolver import _to_snake

    assert _to_snake("data-parallel-size") == "data_parallel_size"
    assert _to_snake("dist-init-addr") == "dist_init_addr"
    assert _to_snake("tensor-parallel-size") == "tensor_parallel_size"
