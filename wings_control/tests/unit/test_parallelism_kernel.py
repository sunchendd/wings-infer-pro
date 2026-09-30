"""并行度公共核单测(DS5/DS2 去重后单一来源)。

锁定 `dp_local_from_device_count`(DP-local 计算+校验)与 `dp_start_rank`(start_rank 公式)行为,
单机 device_count_transform 与多机 coordinate_parallelism 均复用它。
"""

from __future__ import annotations

import logging

import pytest

from wings_ctl.strategy.parallelism import (
    check_capacity,
    dp_local_from_device_count,
    dp_start_rank,
    resolve_replica_tp_dp,
)


def test_dp_local_basic():
    """整除:cnt=16, TP=4 → 4。"""
    assert dp_local_from_device_count(16, 4) == 4


def test_dp_local_tp_one():
    """缺省 TP=1 → DP-local=cnt。"""
    assert dp_local_from_device_count(8, 1) == 8


def test_dp_local_raises_non_positive():
    """cnt≤0 → raise(须为正整数)。"""
    with pytest.raises(ValueError, match="invalid"):
        dp_local_from_device_count(0, 4)


def test_dp_local_raises_less_than_tp():
    """cnt<TP → raise(装不下一个 TP 组)。"""
    with pytest.raises(ValueError, match="insufficient devices"):
        dp_local_from_device_count(2, 4)


def test_dp_local_raises_not_divisible():
    """cnt 非 TP 整数倍 → raise(不向下取整)。"""
    with pytest.raises(ValueError, match="not divisible"):
        dp_local_from_device_count(10, 4)


@pytest.mark.parametrize("bad_tp", [0, -1, -4])
def test_dp_local_raises_non_positive_tp(bad_tp):
    """畸形 recipe 的 TP≤0(除数不合法)→ 友好 ValueError,而非 ZeroDivisionError/静默负值。"""
    with pytest.raises(ValueError, match="tensor_parallel_size"):
        dp_local_from_device_count(4, bad_tp)


def test_dp_start_rank_formula():
    """start_rank = index × dp_local。"""
    assert dp_start_rank(0, 2) == 0
    assert dp_start_rank(1, 2) == 2
    assert dp_start_rank(3, 1) == 3


# ── resolve_replica_tp_dp(R-H:单机够卡调 DP / 少卡收缩 TP)──


def test_replica_ge_tp_adjusts_dp():
    """够卡:cnt=16,TP=8 → TP 不变、DP=2(cnt//tp)。"""
    assert resolve_replica_tp_dp(16, 8) == (8, 2)


def test_replica_eq_tp_dp_one():
    """cnt==TP:TP 不变、DP=1。"""
    assert resolve_replica_tp_dp(8, 8) == (8, 1)


def test_replica_shrink_tp():
    """少卡收缩(核心):cnt=4,TP=8 → TP 收到 4、DP=1(flash 场景)。"""
    assert resolve_replica_tp_dp(4, 8) == (4, 1)


def test_replica_ge_tp_raises_not_divisible():
    """够卡但非整除:cnt=12,TP=8 → raise(不向下取整,R-D)。"""
    with pytest.raises(ValueError, match="not divisible"):
        resolve_replica_tp_dp(12, 8)


def test_replica_shrink_non_power_of_two_warns(caplog):
    """收缩且 cnt 非 2 的幂:cnt=6,TP=8 → 只告警,仍返回 (6, 1)(不再阻断)。"""
    with caplog.at_level(logging.WARNING):
        assert resolve_replica_tp_dp(6, 8) == (6, 1)
    assert "not a power of two" in caplog.text


def test_replica_raises_non_positive():
    """cnt≤0 → raise。"""
    with pytest.raises(ValueError, match="invalid"):
        resolve_replica_tp_dp(0, 8)


@pytest.mark.parametrize("bad_tp", [0, -1])
def test_replica_raises_non_positive_tp(bad_tp):
    """畸形 recipe 的 TP≤0 经 resolve_replica_tp_dp 也友好 ValueError(不崩 ZeroDivisionError)。"""
    with pytest.raises(ValueError, match="tensor_parallel_size"):
        resolve_replica_tp_dp(4, bad_tp)


# ── check_capacity(显存判据,warn-only 内核只返回原因)──


def test_capacity_pass():
    """够装:TP=4×80G=320G ≥ 1.5×200G=300G → 返回 None(裸 gpu_mem,无 util)。"""
    assert check_capacity(4, 80 * 2**30, 200 * 2**30) is None


def test_capacity_reports_insufficient():
    """装不下:TP=4×80G=320G < 1.5×280G=420G → 返回原因字符串,不抛出。"""
    reason = check_capacity(4, 80 * 2**30, 280 * 2**30)
    assert reason is not None and "Insufficient capacity" in reason


def test_capacity_tp_eff_matters():
    """按 TP_有效(非总卡数):同权重 TP=4 装不下、TP=8 装得下。"""
    weight = 200 * 2**30
    assert check_capacity(4, 60 * 2**30, weight) is not None   # 4×60=240 < 300
    assert check_capacity(8, 60 * 2**30, weight) is None       # 8×60=480 ≥ 300
