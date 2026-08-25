"""Unit test — custom PD 黑名单治理(D1 / D2 / D3a)。

覆盖:
- D1: data_parallel_size_local 无条件移出 vllm/vllm-ascend params 黑名单(用户自管)。
- D2: GLOO_SOCKET_IFNAME / NCCL_SOCKET_IFNAME 上移 CONFIG_FILE_ENV_BLACKLIST_COMMON
      (全引擎通用);TP_SOCKET_IFNAME / HCCL_IF_IP 保留引擎级。
- D3a: ASCEND_RT_VISIBLE_DEVICES 属 vllm-ascend env 黑名单;CUDA_VISIBLE_DEVICES 属 vllm。
"""

from __future__ import annotations

import pytest

from wings_ctl.core.config_resolver import (
    CONFIG_FILE_ENV_BLACKLIST_COMMON,
    _config_file_env_blacklist,
    _config_file_params_blacklist,
    _filter_config_file_env_blacklist,
)


# ─── D1: data_parallel_size_local 移出 params 黑名单 ───


@pytest.mark.parametrize("engine", ["vllm", "vllm-ascend"])
def test_d1_size_local_out_of_params_blacklist(engine):
    """data_parallel_size_local 无条件不在 params 黑名单(vllm 系用户自管)。"""
    bl = _config_file_params_blacklist(engine)
    assert "data_parallel_size_local" not in bl
    # start_rank/address 仍由框架派生 → 保留黑名单
    assert "data_parallel_start_rank" in bl
    assert "data_parallel_address" in bl


def test_d1_size_local_never_in_sglang():
    assert "data_parallel_size_local" not in _config_file_params_blacklist("sglang")


# ─── D2: GLOO/NCCL_SOCKET_IFNAME 通用黑名单 ───


def test_d2_socket_ifname_in_common():
    """GLOO/NCCL_SOCKET_IFNAME 在 common 黑名单(全引擎通用)。"""
    assert "GLOO_SOCKET_IFNAME" in CONFIG_FILE_ENV_BLACKLIST_COMMON
    assert "NCCL_SOCKET_IFNAME" in CONFIG_FILE_ENV_BLACKLIST_COMMON


@pytest.mark.parametrize("engine", ["vllm", "vllm-ascend", "sglang"])
def test_d2_socket_ifname_blacklisted_all_engines(engine):
    bl = _config_file_env_blacklist(engine)
    assert "GLOO_SOCKET_IFNAME" in bl
    assert "NCCL_SOCKET_IFNAME" in bl


def test_d2_tp_hccl_stay_engine_level():
    """TP_SOCKET_IFNAME 仅 vllm 系;HCCL_IF_IP 仅 vllm-ascend。"""
    assert "TP_SOCKET_IFNAME" in _config_file_env_blacklist("vllm")
    assert "TP_SOCKET_IFNAME" in _config_file_env_blacklist("vllm-ascend")
    assert "TP_SOCKET_IFNAME" not in _config_file_env_blacklist("sglang")
    assert "HCCL_IF_IP" in _config_file_env_blacklist("vllm-ascend")
    assert "HCCL_IF_IP" not in _config_file_env_blacklist("vllm")
    assert "HCCL_IF_IP" not in CONFIG_FILE_ENV_BLACKLIST_COMMON


# ─── D3a: 可见设备 env 按引擎黑名单 ───


def test_d3a_visible_devices_per_engine():
    assert "ASCEND_RT_VISIBLE_DEVICES" in _config_file_env_blacklist("vllm-ascend")
    assert "ASCEND_RT_VISIBLE_DEVICES" not in _config_file_env_blacklist("vllm")
    assert "CUDA_VISIBLE_DEVICES" in _config_file_env_blacklist("vllm")
    assert "CUDA_VISIBLE_DEVICES" not in _config_file_env_blacklist("vllm-ascend")
    # 两者都不在 common(设备可见性按引擎分配,不是全引擎通用)
    assert "ASCEND_RT_VISIBLE_DEVICES" not in CONFIG_FILE_ENV_BLACKLIST_COMMON
    assert "CUDA_VISIBLE_DEVICES" not in CONFIG_FILE_ENV_BLACKLIST_COMMON


def test_d3a_visible_device_filter_dropped():
    """config-file env 填 CUDA_VISIBLE_DEVICES(vllm)→ 被黑名单弃置。"""
    kept, dropped = _filter_config_file_env_blacklist({"CUDA_VISIBLE_DEVICES": "7", "MY_VAR": "x"}, engine="vllm")
    assert "CUDA_VISIBLE_DEVICES" not in kept
    assert "MY_VAR" in kept
    assert any(d["key"] == "CUDA_VISIBLE_DEVICES" for d in dropped)


def test_d3a_ascend_visible_device_kept_for_vllm():
    """vllm 引擎下 ASCEND_RT_VISIBLE_DEVICES 非黑名单(引擎不匹配)→ 透传。"""
    kept, dropped = _filter_config_file_env_blacklist({"ASCEND_RT_VISIBLE_DEVICES": "2"}, engine="vllm")
    assert "ASCEND_RT_VISIBLE_DEVICES" in kept
    assert dropped == []
