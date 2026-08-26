"""E2E test — 自定义传参方式(--config-file)PD 分离(custom PD)。

覆盖(与 recipe PD 对称,custom 路径):
(a) DP_LOCAL=2 → 2 进程/fail-together/端口 17000..17001/rank 连续/每进程 size_local=1/设备切片。
(b) DP_LOCAL=1 → 1 进程/single/1 endpoint。
(c) config-file 三字段优先;MaaS ENV(六字段)兜底。
(d) blocking 校验(DP_LOCAL<=DP;TP*DP_LOCAL<=device_count)与满卡闭合,文案含生效三元组。
(e) 设备可见性基于 hardware.device(vllm→CUDA_VISIBLE_DEVICES);vllm-ascend→ASCEND_RT_VISIBLE_DEVICES。
(f) env allow_unsafe($(hostname))逐进程保留。
(g) accel 忽略(vllm-ascend 照常支持,不报错)。
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
    EngineVersion,
    ExplicitPdTopology,
    ParallelShape,
    PdRole,
    PdRuntimeInput,
    ResolvedEnv,
    Target,
    UserInput,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware
from wings_ctl.rendering.script_builder import build_scripts

CLI = {"model": "/weights/MiniMax-M3-MXFP8", "served_model_name": "MiniMax-M3-MXFP8"}

# 单 Pod P Instance(nvidia vllm)
PLACEMENT = ClusterPlacement(rank_ip="10.0.0.1", node_ips=["10.0.0.1"], master_ip="10.0.0.1")
EXPLICIT_2P2D = ExplicitPdTopology(
    pd_index=0,
    prefill=ParallelShape(dp_size=2, tp_size=2),
    decode=ParallelShape(dp_size=2, tp_size=2),
    dp_size_local=2,
)


def _pd_input(role=PdRole.PREFILL, explicit=EXPLICIT_2P2D, placement=PLACEMENT) -> PdRuntimeInput:
    return PdRuntimeInput(role=role, placement=placement, explicit_topology=explicit)


def _env(config_root: Path, hardware_info_path: Path, engine="vllm", engine_version="0.19.0") -> ResolvedEnv:
    os.environ["ENGINE_VERSION"] = engine_version
    try:
        hardware = resolve_hardware(hardware_info_path)
        engine_version = resolve_engine_version(config_root, hardware.hardware_family, engine=engine)
        return ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=engine_version)
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def _resolve(
    config_root,
    hardware_info_path,
    *,
    engine="vllm",
    engine_version="0.19.0",
    config_file=None,
    pd_input=None,
    device_count=4,
    user_input=None,
):
    config_file = config_file or CustomConfigFile(params={"max_num_seqs": 256, "tensor_parallel_size": 2}, env={})
    pd_input = pd_input or _pd_input()
    user_input = user_input or UserInput(cli_overrides=CLI)
    return resolve_custom_config(
        _env(config_root, hardware_info_path, engine, engine_version),
        Target(model_name="MiniMax-M3-MXFP8", topology=Topology.PD_PREFILL, engine=engine),
        config_file=config_file,
        user_input=user_input,
        device_count=device_count,
        placement=pd_input.placement,
        pd_input=pd_input,
    )


# ─── (a) DP_LOCAL=2 多进程展开 ───


def test_a_dp_local2_multiprocess(config_root, hardware_info_path):
    resolved = _resolve(config_root, hardware_info_path)
    plan = resolved.process_plan
    assert plan.lifecycle == "fail_together"
    assert plan.endpoints == ["10.0.0.1:17000", "10.0.0.1:17001"]
    assert len(plan.processes) == 2
    # rank 连续;每进程 size_local=1;设备切片按 TP=2 切
    for i, p in enumerate(plan.processes):
        assert p.dp_rank == i
        assert p.process_index == i
        assert p.visible_devices == (i * 2, i * 2 + 1)
        argv = shlex.join(p.argv)
        assert f"--port 1700{i}" in argv
        assert "--data-parallel-size-local 1" in argv
        assert f"--data-parallel-rank {i}" in argv
        assert "--data-parallel-size 2" in argv
        assert "--data-parallel-address 10.0.0.1" in argv


def test_a1_dp_local2_render_fail_together(config_root, hardware_info_path, tmp_path):
    resolved = _resolve(config_root, hardware_info_path)
    sp, rp = build_scripts(resolved, tmp_path)
    txt = sp.read_text()
    assert "trap terminate_children EXIT TERM INT" in txt
    assert "pids+=(" in txt
    assert "process[0] rank=0" in txt and "process[1] rank=1" in txt
    # 每进程独立 CUDA_VISIBLE_DEVICES
    assert "export CUDA_VISIBLE_DEVICES=0,1" in txt
    assert "export CUDA_VISIBLE_DEVICES=2,3" in txt


# ─── (b) DP_LOCAL=1 单进程 ───


def test_b_dp_local1_single(config_root, hardware_info_path):
    explicit1 = ExplicitPdTopology(
        pd_index=0,
        prefill=ParallelShape(dp_size=1, tp_size=4),
        decode=ParallelShape(dp_size=1, tp_size=4),
        dp_size_local=1,
    )
    pd_input = _pd_input(explicit=explicit1)
    # config_file 不填 TP(避免覆盖 MaaS TP=4):走 MaaS 兜底
    resolved = _resolve(
        config_root,
        hardware_info_path,
        pd_input=pd_input,
        config_file=CustomConfigFile(params={}, env={}),
        device_count=4,
    )
    plan = resolved.process_plan
    assert plan.lifecycle == "single"
    assert plan.endpoints == ["10.0.0.1:17000"]
    assert len(plan.processes) == 1
    p = plan.processes[0]
    assert p.visible_devices == (0, 1, 2, 3)
    assert p.dp_rank is None
    assert not any(argument.startswith("--data-parallel-") for argument in p.argv)


def test_b1_dp1_external_lb_warn_only(config_root, hardware_info_path):
    """验证 custom PD 对 DP=1 显式 external LB 仅告警、不阻断,且不派生 data_parallel_rank。"""
    explicit1 = ExplicitPdTopology(
        pd_index=0,
        prefill=ParallelShape(dp_size=1, tp_size=4),
        decode=ParallelShape(dp_size=1, tp_size=4),
        dp_size_local=1,
    )

    resolved = _resolve(
        config_root,
        hardware_info_path,
        pd_input=_pd_input(explicit=explicit1),
        config_file=CustomConfigFile(params={"data_parallel_external_lb": True}, env={}),
        device_count=4,
    )
    plan = resolved.process_plan
    assert plan is not None
    assert len(plan.processes) == 1
    process = plan.processes[0]
    assert process.dp_rank is None
    argv = shlex.join(process.argv)
    assert "--data-parallel-rank" not in argv
    # 用户自管的 external_lb 原样保留,仅告警;rank 不派生。
    assert "--data-parallel-external-lb" in argv
    assert "data_parallel_external_lb" in resolved.resolution_notes["custom_pd_device_capacity"]


# ─── (c) config-file 优先,MaaS 兜底 ───


def test_c_config_file_tp_overrides_maas(config_root, hardware_info_path):
    """config-file 填 TP=4 覆盖 MaaS TP=2;validate+闭合按 config-file 值。"""
    cf = CustomConfigFile(params={"tensor_parallel_size": 4}, env={})
    # MaaS TP=2 DP_LOCAL=2;config TP=4 → 生效 TP=4,DP_LOCAL=2 → 需 8 卡闭合
    resolved = _resolve(config_root, hardware_info_path, config_file=cf, device_count=8)
    plan = resolved.process_plan
    assert len(plan.processes) == 2
    assert plan.processes[0].visible_devices == (0, 1, 2, 3)
    assert "--tensor-parallel-size 4" in shlex.join(plan.processes[0].argv)


def test_c1_maas_fallback_when_config_missing(config_root, hardware_info_path):
    """config-file 未填 TP/DP_LOCAL → 用 MaaS ENV 六字段兜底(DP=2/TP=2/DP_LOCAL=2)。"""
    cf = CustomConfigFile(params={"max_num_seqs": 64}, env={})
    resolved = _resolve(config_root, hardware_info_path, config_file=cf, device_count=4)
    plan = resolved.process_plan
    assert len(plan.processes) == 2
    argv = shlex.join(plan.processes[0].argv)
    assert "--tensor-parallel-size 2" in argv
    assert "--data-parallel-size 2" in argv


def test_c2_config_file_size_local_wins(config_root, hardware_info_path):
    """custom PD:用户 config-file 填 data_parallel_size_local 优先于 MaaS ENV。"""
    # MaaS DP_LOCAL=2;用户 config 填 DP_LOCAL=1 + DP=1(单 Pod → global DP=1 闭合)
    cf = CustomConfigFile(
        params={
            "data_parallel_size_local": 1,
            "data_parallel_size": 1,
            "data_parallel_rpc_port": 12345,
        },
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, config_file=cf, device_count=2)
    plan = resolved.process_plan
    assert plan.lifecycle == "single"
    assert len(plan.processes) == 1
    assert plan.processes[0].dp_rank is None
    argv = shlex.join(plan.processes[0].argv)
    # DP=1 仅跳过平台派生的 data_parallel_rank;用户自管参数原样保留。
    assert "--data-parallel-rank" not in argv
    assert "--data-parallel-size 1" in argv
    assert "--data-parallel-size-local 1" in argv
    assert "--data-parallel-rpc-port 12345" in argv


# ─── (d) blocking 校验 ───


def test_d_missing_maas_and_config_blocks(config_root, hardware_info_path):
    """PD 六字段缺失且 config-file 也未填 DP/TP/DP_LOCAL → fail-fast。"""
    pd_input = PdRuntimeInput(role=PdRole.PREFILL, placement=PLACEMENT, explicit_topology=None)
    with pytest.raises(ValueError, match=r"data_parallel_size is missing or invalid"):
        _resolve(config_root, hardware_info_path, pd_input=pd_input, device_count=4)


def test_d1_dp_local_gt_dp_warn_only(config_root, hardware_info_path):
    """DP_LOCAL > DP → **仅告警,不阻断**(已确认并行准确性交用户负责)。"""
    explicit = ExplicitPdTopology(
        pd_index=0,
        prefill=ParallelShape(dp_size=2, tp_size=2),
        decode=ParallelShape(dp_size=2, tp_size=2),
        dp_size_local=4,  # > DP=2
    )
    pd_input = _pd_input(explicit=explicit)
    cf = CustomConfigFile(
        params={
            "kv_transfer_config": {
                "kv_connector_extra_config": {
                    "prefill": {"dp_size": 2, "tp_size": 2},
                    "decode": {"dp_size": 2, "tp_size": 2},
                }
            }
        },
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=8)
    # 不 raise;DP_LOCAL>DP 记入告警
    assert resolved.process_plan is not None
    assert "DP_LOCAL=4 > DP=2" in resolved.resolution_notes["custom_pd_device_capacity"]


def test_d2_capacity_warning_not_block(config_root, hardware_info_path):
    """容量不足**不阻断**(已确认卡数准确性交用户负责),但记 warning 审计。

    修订:去掉满卡闭合(TP*DP_LOCAL==device_count)与容量不足阻塞;TP*DP_LOCAL>device_count
    仅记 custom_pd_device_capacity 告警,启动照常。DP_LOCAL<=DP 也仅告警(不阻断,test_d1)。
    """
    explicit = ExplicitPdTopology(
        pd_index=0,
        prefill=ParallelShape(dp_size=2, tp_size=4),
        decode=ParallelShape(dp_size=2, tp_size=4),
        dp_size_local=2,
    )
    pd_input = _pd_input(explicit=explicit)
    # 填 extra config,避免「未抽到对侧」告警干扰本用例(专注测容量告警)
    cf = CustomConfigFile(
        params={
            "kv_transfer_config": {
                "kv_connector_extra_config": {
                    "prefill": {"dp_size": 2, "tp_size": 4},
                    "decode": {"dp_size": 2, "tp_size": 4},
                }
            }
        },
        env={},
    )
    # TP=4*DP_LOCAL=2=8 == device_count=8 → 满卡闭合,无告警
    resolved = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=8)
    assert len(resolved.process_plan.processes) == 2
    assert "custom_pd_device_capacity" not in resolved.resolution_notes
    # device_count=10(required=8 ≤ 10 → 容量足够,不阻断、无告警;且不再要求满卡==)
    resolved2 = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=10)
    assert len(resolved2.process_plan.processes) == 2
    assert "custom_pd_device_capacity" not in resolved2.resolution_notes
    # device_count=4(required=8 > 4 → 容量不足)→ 不阻断,但记 warning 审计
    resolved3 = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=4)
    assert len(resolved3.process_plan.processes) == 2
    assert "device_count=4" in resolved3.resolution_notes["custom_pd_device_capacity"]


# ─── (e) 设备可见性基于 hardware.device ───


def test_e_vllm_cuda_visible_devices(config_root, hardware_info_path):
    resolved = _resolve(config_root, hardware_info_path)
    env0 = resolved.process_plan.processes[0].env_traces
    assert env0["CUDA_VISIBLE_DEVICES"].final_value == "0,1"
    assert "ASCEND_RT_VISIBLE_DEVICES" not in env0


def test_e1_device_visible_env_blacklisted(config_root, hardware_info_path):
    """CUDA_VISIBLE_DEVICES 属 vllm env 黑名单:config-file 填了也被弃,由框架派生。"""
    cf = CustomConfigFile(params={}, env={"CUDA_VISIBLE_DEVICES": "7"})
    resolved = _resolve(config_root, hardware_info_path, config_file=cf)
    dropped = {d["key"] for d in resolved.config_file_params if d["status"] == "dropped"}
    assert "CUDA_VISIBLE_DEVICES" in dropped
    # 派生值未被覆盖(仍为框架切片)
    assert resolved.process_plan.processes[0].env_traces["CUDA_VISIBLE_DEVICES"].final_value == "0,1"


# ─── (f) env allow_unsafe 逐进程保留 ───


def test_f_env_allow_unsafe_preserved(config_root, hardware_info_path, tmp_path):
    cf = CustomConfigFile(params={}, env={"MY_VAR": "$(hostname)"})
    resolved = _resolve(config_root, hardware_info_path, config_file=cf)
    for p in resolved.process_plan.processes:
        tr = p.env_traces["MY_VAR"]
        assert tr.allow_unsafe is True
        assert tr.final_value == "$(hostname)"
    sp, rp = build_scripts(resolved, tmp_path)
    txt = sp.read_text()
    assert 'export MY_VAR="$(hostname)"' in txt


# ─── (g) accel 忽略 ───


def test_g_accel_ignored_no_error(config_root, hardware_info_path):
    """PD custom 即使开启 accel 开关也不报错(与 recipe PD 不同,accel 完全忽略)。"""
    os.environ["SMART_ACCEL_ENABLED"] = "true"
    try:
        resolved = _resolve(config_root, hardware_info_path)
        assert resolved.process_plan is not None
        # accel 产物为空(不 merge)
        # 注:此处仅验证不抛错;accel 开关若导致 apply_smart_accel 被调用需 config 资产,
        # 因此 custom PD 路径必须绕过 accel 收集。
    finally:
        os.environ.pop("SMART_ACCEL_ENABLED", None)


# ─── (h) engine_id 派生 + audit ───


def test_h_engine_id_derived_from_pd_index(config_root, hardware_info_path):
    """engine_id 恒由 PD_INDEX(pd_index)派生,并注入每进程 kv_transfer_config。"""
    # PD_INDEX=7
    explicit = ExplicitPdTopology(
        pd_index=7,
        prefill=ParallelShape(dp_size=2, tp_size=2),
        decode=ParallelShape(dp_size=2, tp_size=2),
        dp_size_local=2,
    )
    resolved = _resolve(config_root, hardware_info_path, pd_input=_pd_input(explicit=explicit))
    plan = resolved.process_plan
    for p in plan.processes:
        # process_plan engine_config_traces 已含 kv_transfer_config.engine_id
        kv = p.engine_config_traces["kv_transfer_config"].final_value
        assert kv["engine_id"] == "7"
    # audit
    assert resolved.pd_engine_id_audit["engine_id"] == "7"
    assert resolved.pd_engine_id_audit["pd_index"] == 7
    assert resolved.resolution_notes["custom_pd_engine_id"] == "7"


def test_h1_engine_id_overrides_user_value(config_root, hardware_info_path):
    """用户填 engine_id 也由派生层覆盖(派生优先级高于 config-file);audit 记录 user_value。"""
    # PD_INDEX=0;config-file 填 kv_transfer_config.engine_id=99
    pg_cf = CustomConfigFile(
        params={
            "kv_transfer_config": {
                "kv_connector": "MooncakeHybridConnector",
                "kv_role": "kv_producer",
                "engine_id": 99,
            }
        },
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, config_file=pg_cf)
    kv = resolved.process_plan.processes[0].engine_config_traces["kv_transfer_config"].final_value
    # 用户 key 保留,engine_id 被强制为 PD_INDEX=0
    assert kv["kv_role"] == "kv_producer"
    assert kv["engine_id"] == "0"
    assert resolved.pd_engine_id_audit["user_value"] == 99


def test_i_parallel_resolution_audit(config_root, hardware_info_path):
    """pd_parallel_resolution 逐字段审计(config_file 优先 / MaaS 兜底 / source/status/maas_env)。"""
    # MaaS: DP=2/TP=2/DP_LOCAL=2;config 填 DP=2(与 MaaS 一致) + TP=4(与 MaaS 不一致)
    pg_cf = CustomConfigFile(params={"data_parallel_size": 2, "tensor_parallel_size": 4}, env={})
    resolved = _resolve(config_root, hardware_info_path, config_file=pg_cf, device_count=8)
    res = {r["field"]: r for r in resolved.pd_parallel_resolution}
    # DP:用户与 MaaS 一致
    assert res["data_parallel_size"]["source"] == "config_file"
    assert res["data_parallel_size"]["status"] == "consistent"
    assert res["data_parallel_size"]["effective_value"] == 2
    # TP:用户配置优先,与 MaaS 不一致 → mismatch/warning
    assert res["tensor_parallel_size"]["source"] == "config_file"
    assert res["tensor_parallel_size"]["status"] == "mismatch"
    assert res["tensor_parallel_size"]["severity"] == "warning"
    assert res["tensor_parallel_size"]["effective_value"] == 4
    assert res["tensor_parallel_size"]["maas_env"] == "PD_PREFILL_TP_SIZE"
    # DP_LOCAL:用户未填 → MaaS 兜底 → fallback
    assert res["data_parallel_size_local"]["source"] == "maas_env"
    assert res["data_parallel_size_local"]["status"] == "fallback"
    assert res["data_parallel_size_local"]["effective_value"] == 2
    assert res["data_parallel_size_local"]["maas_env"] == "DP_SIZE_LOCAL"


# ─── (j) 跨 Pod PD(特殊 multi_node 基线) ───


def test_j_cross_pod_inherits_multinode_baseline(config_root, hardware_info_path):
    """跨 Pod PD 继承 multi_node 基线:nnodes/node_rank/master_addr + 网络 env。"""
    placement2 = ClusterPlacement(rank_ip="10.0.0.2", node_ips=["10.0.0.1", "10.0.0.2"], master_ip="10.0.0.1")
    explicit = ExplicitPdTopology(
        pd_index=0,
        prefill=ParallelShape(dp_size=4, tp_size=2),
        decode=ParallelShape(dp_size=4, tp_size=2),
        dp_size_local=2,
    )
    resolved = _resolve(
        config_root,
        hardware_info_path,
        pd_input=_pd_input(explicit=explicit, placement=placement2),
    )
    plan = resolved.process_plan
    p0 = plan.processes[0]
    ec = p0.engine_config_traces
    # 继承 multi_node 身份键(rank_ip=10.0.0.2 是第 2 个节点 → node_rank=1)
    assert ec["nnodes"].final_value == 2
    assert ec["node_rank"].final_value == 1
    assert ec["master_addr"].final_value == "10.0.0.1"
    # 身份层:engine_id from PD_INDEX
    assert ec["kv_transfer_config"].final_value["engine_id"] == "0"
    # 每个 local process 仍是 per-rank(size_local=1),Pod 级 DP_LOCAL=2
    for p in plan.processes:
        assert "--data-parallel-size-local 1" in shlex.join(p.argv)
    assert len(plan.processes) == 2
    # 跨 Pod 网络 env 继承:nvidia vllm → GLOO/NCCL 网卡声明经 apply_network_env_strategy 覆盖
    env_keys = set(p0.env_traces.keys())
    assert "GLOO_SOCKET_IFNAME" in env_keys or "NCCL_SOCKET_IFNAME" in env_keys
    # 跨 Pod 标记写入 notes
    assert resolved.resolution_notes["custom_pd_is_cross_pod"] == "yes"


def test_j1_sglang_entry_blocked(config_root, hardware_info_path):
    """PD 场景 sglang 引擎在入口被拦截(明确文案)。"""
    hardware = resolve_hardware(hardware_info_path)
    env = ResolvedEnv(
        config_root=config_root,
        hardware=hardware,
        engine_version=EngineVersion(requested="v0.5.10", resolved="v0.5.10", is_fallback=False),
    )
    with pytest.raises(NotImplementedError, match="sglang"):
        resolve_custom_config(
            env,
            Target(model_name="MiniMax-M3-MXFP8", topology=Topology.PD_PREFILL, engine="sglang"),
            config_file=CustomConfigFile(params={"max_num_seqs": 256, "tensor_parallel_size": 2}, env={}),
            user_input=UserInput(cli_overrides=CLI),
            device_count=4,
            placement=PLACEMENT,
            pd_input=_pd_input(),
        )


# ─── (k) 对侧 shape 缺失: -1 哨兵 + 告警,不阻塞;当前 role 用 effective 兜底 ───


def test_k_peer_unknown_sentinel_and_warn(config_root, hardware_info_path):
    """decode Pod 的 extra_config 只填 decode 侧 → prefill(对侧)以 -1 标记+告警,不阻塞。

    同时验证:当前 role(decode)shape 用 extra_config 真实值;prefill 对侧缺字段为 -1;
    进程数/rank 以 effective 的 DP_LOCAL 为准,与对侧无关。
    """
    explicit = ExplicitPdTopology(
        pd_index=1,
        prefill=ParallelShape(dp_size=2, tp_size=2),
        decode=ParallelShape(dp_size=2, tp_size=2),
        dp_size_local=2,
    )
    pd_input = _pd_input(role=PdRole.DECODE, explicit=explicit)
    # 只填 decode 侧(prefill 侧缺失),且 dp 只填一个、tp 缺失 → 逐字段独立
    cf = CustomConfigFile(
        params={"kv_transfer_config": {"kv_connector_extra_config": {"decode": {"dp_size": 2}}}},
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=8)
    # 不阻塞;进程数以 effective DP_LOCAL=2 展开
    assert resolved.process_plan is not None
    assert len(resolved.process_plan.processes) == 2
    # 对侧(prefill)缺字段 → -1 哨兵 + 告警
    assert resolved.pd_topology.prefill.dp_size == -1  # decode pod 对侧 prefill
    assert resolved.pd_topology.prefill.tp_size == -1
    # 当前 role(decode):dp 用 extra_config 的 2;缺的 tp 用 effective 兜底(=explicit.decode.tp=2)
    assert resolved.pd_topology.decode.dp_size == 2
    assert resolved.pd_topology.decode.tp_size == 2
    assert "peer" in resolved.resolution_notes.get("custom_pd_device_capacity", "")


def test_k1_prefill_side_peer_unknown(config_root, hardware_info_path):
    """prefill Pod 的 extra_config 只填 prefill → decode(对侧)以 -1 标记+告警。"""
    pd_input = _pd_input(role=PdRole.PREFILL, explicit=EXPLICIT_2P2D)
    cf = CustomConfigFile(
        params={"kv_transfer_config": {"kv_connector_extra_config": {"prefill": {"dp_size": 2, "tp_size": 2}}}},
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=8)
    assert resolved.process_plan is not None
    # 对侧(decode)缺字段 → -1
    assert resolved.pd_topology.decode.dp_size == -1
    assert resolved.pd_topology.decode.tp_size == -1
    # 当前 role(prefill)用 extra_config 真实值
    assert resolved.pd_topology.prefill.dp_size == 2
    assert resolved.pd_topology.prefill.tp_size == 2
    assert "peer" in resolved.resolution_notes.get("custom_pd_device_capacity", "")


# ─── (l) input_policy 恒为 custom_config(不复用 recipe derived/explicit) ───


def test_l_input_policy_always_custom_config(config_root, hardware_info_path):
    """MaaS 六字段有无都不影响 input_policy 归类,恒为 custom_config(设计 §4)。"""
    # 有六字段(explicit 提供) → custom_config
    resolved_explicit = _resolve(config_root, hardware_info_path)
    assert resolved_explicit.pd_topology.input_policy == "custom_config"
    assert resolved_explicit.resolution_notes["pd_topology_input_policy"] == "custom_config"
    # 无六字段(explicit=None,并行度全由 config-file 提供)→ 也归 custom_config
    pd_input = _pd_input(explicit=None)
    cf = CustomConfigFile(
        params={"data_parallel_size": 2, "tensor_parallel_size": 2, "data_parallel_size_local": 2}, env={}
    )
    resolved_no_maas = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=4)
    assert resolved_no_maas.pd_topology.input_policy == "custom_config"
    assert resolved_no_maas.resolution_notes["pd_topology_input_policy"] == "custom_config"


# ─── (m) 无 MaaS 六字段:并行度全由 config-file 提供 ───


def test_m_no_maas_six_fields_config_only(config_root, hardware_info_path):
    """explicit=None + config-file 提供 DP/TP/DP_LOCAL → 以 config-file 并行度展开。

    验证:无六字段不复用 recipe 的 derived_1p1d 语义(P/D 恒 1、fixed rank),而是真实采用
    config-file 的 DP_LOCAL(=2)展开 2 进程;instance_index 按 role 兜底(P=0/D=1)。
    """
    pd_input = _pd_input(role=PdRole.PREFILL, explicit=None)
    cf = CustomConfigFile(
        params={"data_parallel_size": 2, "tensor_parallel_size": 2, "data_parallel_size_local": 2},
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=4)
    plan = resolved.process_plan
    # 展开 2 进程(DP_LOCAL=2 真实采用,而非 recipe 固定 1 进程)
    assert len(plan.processes) == 2
    assert plan.endpoints == ["10.0.0.1:17000", "10.0.0.1:17001"]
    for i, p in enumerate(plan.processes):
        assert p.dp_rank == i
        assert "--data-parallel-size-local 1" in shlex.join(p.argv)
    # instance_index 无六字段 → 按 role 兜底:PREFILL=0
    assert resolved.pd_topology.instance_index == 0
    assert resolved.pd_engine_id_audit["engine_id"] == "0"


def test_m1_no_maas_decode_instance_index_blocked(config_root, hardware_info_path):
    """无六字段 decode Pod → instance_index 兜底为 1。"""
    pd_input = _pd_input(role=PdRole.DECODE, explicit=None)
    cf = CustomConfigFile(
        params={"data_parallel_size": 2, "tensor_parallel_size": 2, "data_parallel_size_local": 2},
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=4)
    assert resolved.pd_topology.instance_index == 1
    assert resolved.pd_engine_id_audit["engine_id"] == "1"


def test_m2_no_maas_stdout_role_shape_effective_fallback(config_root, hardware_info_path):
    """无六字段:current role 的 P/D shape 用 effective 兜底(非 -1 守卫)。"""
    pd_input = _pd_input(role=PdRole.PREFILL, explicit=None)
    cf = CustomConfigFile(
        params={"data_parallel_size": 3, "tensor_parallel_size": 2, "data_parallel_size_local": 2},
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=6)
    # 当前 role(prefill)用 effective 兜底(非 -1);对侧(decode)未知 → -1
    assert resolved.pd_topology.prefill.dp_size == 3
    assert resolved.pd_topology.prefill.tp_size == 2
    assert resolved.pd_topology.decode.dp_size == -1
    assert resolved.pd_topology.decode.tp_size == -1


def test_m3_no_maas_no_next_size_device_count_required(config_root, hardware_info_path):
    """无六字段 + device_count 不足 → 仅容卡告警不阻断。"""
    pd_input = _pd_input(role=PdRole.PREFILL, explicit=None)
    cf = CustomConfigFile(
        params={"data_parallel_size": 2, "tensor_parallel_size": 2, "data_parallel_size_local": 2},
        env={},
    )
    resolved = _resolve(config_root, hardware_info_path, pd_input=pd_input, config_file=cf, device_count=2)
    assert resolved.process_plan is not None
    assert len(resolved.process_plan.processes) == 2
    assert "device_count=2" in resolved.resolution_notes["custom_pd_device_capacity"]


# ─── (n) 引擎白名单(新增引擎未登记 → 入口显式拒绝,而非静默崩溃) ───


def test_n_unregistered_engine_mindie_entry_blocked(config_root, hardware_info_path):
    """白名单外引擎(如 mindie)在入口被 NotImplementedError 显式拒绝。"""
    with pytest.raises(NotImplementedError, match="does not support engine mindie"):
        _resolve(config_root, hardware_info_path, engine="mindie")


def test_n1_engine_whitelist_sglang(config_root, hardware_info_path):
    """sglang 属白名单外 → 入口以 NotImplementedError 明确拒绝(不被通用 validate_* 先抛 ValueError 掩盖)。"""
    hardware = resolve_hardware(hardware_info_path)
    env = ResolvedEnv(
        config_root=config_root,
        hardware=hardware,
        engine_version=EngineVersion(requested="v0.5.10", resolved="v0.5.10", is_fallback=False),
    )
    with pytest.raises(NotImplementedError, match="sglang"):
        resolve_custom_config(
            env,
            Target(model_name="MiniMax-M3-MXFP8", topology=Topology.PD_PREFILL, engine="sglang"),
            config_file=CustomConfigFile(params={"max_num_seqs": 256, "tensor_parallel_size": 2}, env={}),
            user_input=UserInput(cli_overrides=CLI),
            device_count=4,
            placement=PLACEMENT,
            pd_input=_pd_input(),
        )


def test_n2_engine_whitelist_vllm_ascend_ok(config_root, hardware_info_path):
    """vllm-ascend 在白名单内 → 正常解析(进程布局与 vllm 共用派先器)。"""
    resolved = _resolve(config_root, hardware_info_path, engine="vllm-ascend")
    assert resolved.process_plan is not None
    assert len(resolved.process_plan.processes) == 2


# ─── (o) custom_pd_device_capacity 投影到 wings_start.log 的 [STARTUP] WARNING ───


def test_o_custom_warning_projected_to_startup_log(config_root, hardware_info_path, tmp_path, monkeypatch):
    """DP_LOCAL>DP 或容量不足等 custom PD warn-only → 投影到 wings_start.log 的 WARNING 行。

    验证 _build_summary_lines:有 custom_pd_device_capacity 时追加
    ``[STARTUP] WARNING: <文案>``,使用户在 host 日志可见(而非仅存 audit.json)。
    """
    from wings_ctl.audit.startup_log import _build_summary_lines

    resolved = _resolve(config_root, hardware_info_path)
    # 让 custom_pd_device_capacity 存在(手动注入即可,专注投影层)
    resolved.resolution_notes["custom_pd_device_capacity"] = "DP_LOCAL=2 > DP=2; peer warning"
    artifact_paths = {
        "start": tmp_path / "start_command.sh",
        "repro": tmp_path / "repro.sh",
        "audit": tmp_path / "audit.json",
        "output_dir": tmp_path,
        "model_name": "MiniMax-M3-MXFP8",
    }
    lines = _build_summary_lines(resolved, artifact_paths, tmp_path / "wings_start.log")
    assert "[STARTUP] WARNING: DP_LOCAL=2 > DP=2; peer warning" in lines


# ─── (p) 当前 role 实际并行度唯一权威 = effective(顶层),nested 冲突不覆盖、仅告警 ───


def test_p_top_level_effective_is_authoritative_over_nested(config_root, hardware_info_path):
    """顶层 effective 与实际 argv 必须一致,即使 nested kv_connector_extra_config 与之冲突。

    - 顶层 TP=4、current role(prefill)nested tp=2 冲突 → 最终 argv/进程布局用 effective=4;
    - pd_parallel_resolution 记 4;
    - custom_pd_device_capacity 含"两者不一致"的英文 warning,不阻断。
    """
    cf = CustomConfigFile(
        params={
            "max_num_seqs": 256,
            "data_parallel_size": 2,
            "tensor_parallel_size": 4,
            "data_parallel_size_local": 2,
            "kv_transfer_config": {
                "kv_connector_extra_config": {
                    "prefill": {"dp_size": 2, "tp_size": 2},
                    "decode": {"dp_size": 2, "tp_size": 2},
                }
            },
        },
        env={},
    )
    resolved = _resolve(
        config_root, hardware_info_path, config_file=cf, device_count=16
    )
    assert len(resolved.process_plan.processes) == 2
    argv = shlex.join(resolved.process_plan.processes[0].argv)
    # 冲突时最终 argv 用顶层 effective=4(而非 nested prefill tp=2)
    assert "--tensor-parallel-size 4" in argv
    # pd_parallel_resolution 与 argv 一致
    res = {r["field"]: r for r in resolved.pd_parallel_resolution}
    assert res["tensor_parallel_size"]["effective_value"] == 4
    assert res["data_parallel_size"]["effective_value"] == 2
    # 不阻断,但有英文 warning 记录两者不一致
    capacity_note = resolved.resolution_notes.get("custom_pd_device_capacity", "")
    assert "differs from" in capacity_note
    assert "using top-level effective" in capacity_note
