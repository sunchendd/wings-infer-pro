"""LMCache per-worker 容量按卡数(gpu_count)均分的回归测试。"""

from __future__ import annotations

from wings_accel import resolve_smart_accel_from_config
from wings_accel.yaml_loader import LoadFlags

_ASSET_KW = {
    "engine": "vllm-ascend",
    "engine_version": "v0.21.0rc",
    "hardware_family": "ascend-a3",
    "model_name": "DeepSeek-V4-Flash-w8a8-mtp",
}


def _resolve(flags: LoadFlags, gpu_count: int = 1):
    return resolve_smart_accel_from_config(config_root="", gpu_count=gpu_count, flags=flags, **_ASSET_KW)


def test_numeric_quota_split_by_device_count():
    """数值配额按卡数均分:16GB / 8 卡 = 2,不受 recipe 静态 tp/dp(4×4)影响。"""
    out = _resolve(
        LoadFlags(kv=True, memory_offload_size_mode="16", tp_size=4, dp_size=4, gpu_count=8),
        gpu_count=8,
    )
    assert out is not None
    assert out.engine_params.env["LMCACHE_MAX_LOCAL_CPU_SIZE"] == "2"
    assert out.kv_mem_offload_size_gb == 16


def test_auto_estimate_uses_device_count_workers():
    """auto 估算 worker 数取卡数:512G/8 worker → 容量 401;均分 401//8=50。"""
    out = _resolve(
        LoadFlags(
            kv=True,
            memory_offload_size_mode="auto",
            pod_available_memory_gb=512,
            tp_size=4,
            dp_size=4,
            gpu_count=8,
        ),
        gpu_count=8,
    )
    assert out is not None
    assert out.kv_mem_offload_size_gb == 401
    assert out.engine_params.env["LMCACHE_MAX_LOCAL_CPU_SIZE"] == "50"


def test_gpu_count_injected_before_load_for_estimation():
    """resolve 入参 gpu_count 在 load 之前进入 flags:估算阶段即可生效(时序修复)。"""
    out = _resolve(
        LoadFlags(
            kv=True,
            memory_offload_size_mode="auto",
            pod_available_memory_gb=512,
            tp_size=4,
            dp_size=4,
        ),
        gpu_count=8,
    )
    assert out is not None
    assert out.kv_mem_offload_size_gb == 401
    assert out.engine_params.env["LMCACHE_MAX_LOCAL_CPU_SIZE"] == "50"


# ── MiniMax-M2.7-nvfp4(GPU/LMCacheConnectorV1,cpu+cpu_disk scheme)──

_MINIMAX_KW = {
    "engine": "vllm",
    "engine_version": "v0.23.0",
    "hardware_family": "rtx_pro_5000_48G",
    "model_name": "MiniMax-M2.7-nvfp4",
}


def _resolve_minimax(flags: LoadFlags, gpu_count: int = 1):
    return resolve_smart_accel_from_config(config_root="", gpu_count=gpu_count, flags=flags, **_MINIMAX_KW)


def test_minimax_cpu_disk_split_by_device_count():
    """cpu_disk scheme:CPU/DISK 配额均按卡数均分,8 worker 总量恰好等于 Pod 配额。"""
    out = _resolve_minimax(
        LoadFlags(
            kv=True,
            memory_offload_size_mode="160",
            tp_size=4,
            dp_size=1,
            disk=True,
            disk_gb=400,
            disk_path="/lmcache",
            topology="standalone",
        ),
        gpu_count=8,
    )
    assert out is not None
    env = out.engine_params.env
    # 160//8=20、400//8=50(×8 worker 恰好等于配额)。
    assert env["LMCACHE_MAX_LOCAL_CPU_SIZE"] == "20"
    assert env["LMCACHE_MAX_LOCAL_DISK_SIZE"] == "50"
    assert env["LMCACHE_LOCAL_DISK"] == "/lmcache"


def test_minimax_cpu_only_split_by_device_count():
    """cpu scheme(无磁盘):8 卡时 160//8=20,不再随静态 tp_size 超配。"""
    out = _resolve_minimax(
        LoadFlags(
            kv=True,
            memory_offload_size_mode="160",
            tp_size=4,
            dp_size=1,
            topology="multi_node",
        ),
        gpu_count=8,
    )
    assert out is not None
    assert out.engine_params.env["LMCACHE_MAX_LOCAL_CPU_SIZE"] == "20"


def test_minimax_single_replica_matches_old_behavior():
    """卡数=TP(单副本 DP=1)时 gpu_count == tp_size,结果与旧表达式一致(兼容锚点)。"""
    out = _resolve_minimax(
        LoadFlags(
            kv=True,
            memory_offload_size_mode="160",
            tp_size=4,
            dp_size=1,
            topology="standalone",
        ),
        gpu_count=4,
    )
    assert out is not None
    assert out.engine_params.env["LMCACHE_MAX_LOCAL_CPU_SIZE"] == "40"
