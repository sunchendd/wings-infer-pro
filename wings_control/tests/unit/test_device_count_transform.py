"""DeviceCountTransform(小策略层)边界单测。

覆盖 device-count 协调的全部分支:不触发 / 整除覆盖 DP / 等模板 no-op /
cnt<M 收缩 TP(R-H,2 幂)/ cnt<M 非 2 幂 raise / cnt%M≠0 raise /
cnt≥M 时 TP 永不计算 / 模板缺 TP 时缺省 1。
对应实现 src/wings_ctl/strategy/post_template.py::device_count_transform。
"""

from __future__ import annotations

import pytest

from wings_ctl.strategy.post_template import device_count_transform


def _cfg(tp: int = 4, dp: int = 4) -> dict:
    """构造模板 engine_config:tensor_parallel_size=tp(=M)、data_parallel_size=dp。"""
    return {"tensor_parallel_size": tp, "data_parallel_size": dp, "model": "acme/m"}


def test_not_triggered_without_device_count() -> None:
    """未下发 device_count(None)→ 不触发,override/notes 皆空。"""
    override, notes = device_count_transform(_cfg(), {"device_count": None})
    assert not override
    assert not notes


def test_integer_multiple_overrides_dp() -> None:
    """整除场景:M=4、cnt=8 → DP=2(≠模板 4)→ 产覆盖层,status=overridden。"""
    override, notes = device_count_transform(_cfg(tp=4, dp=4), {"device_count": 8})
    assert override == {"data_parallel_size": 2}
    assert notes["device_count_status"] == "overridden"
    assert notes["device_count_resolved_dp"] == "2"
    assert notes["device_count_tp"] == "4"


def test_equals_template_is_noop() -> None:
    """结果等于模板:M=4、cnt=16 → DP=4==模板 → 不产 override,仅记 noop status。"""
    override, notes = device_count_transform(_cfg(tp=4, dp=4), {"device_count": 16})
    assert not override
    assert notes["device_count_status"] == "noop_equals_template"
    assert notes["device_count_resolved_dp"] == "4"


def test_cnt_less_than_m_shrinks_tp() -> None:
    """R-H:cnt<M 且 cnt 为 2 幂(2<4)→ 收缩 TP=2、DP=1,status=tp_shrunk。

    (前置显存闸/heads 守卫在 resolve_config 跑,单测直调 transform 不含闸。)
    """
    override, notes = device_count_transform(_cfg(tp=4), {"device_count": 2})
    assert override == {"tensor_parallel_size": 2, "data_parallel_size": 1}
    assert notes["device_count_status"] == "tp_shrunk"
    assert notes["device_count_tp_eff"] == "2"


def test_cnt_less_than_m_non_power_of_two_raises() -> None:
    """R-H:cnt<M 但非 2 的幂(3<4)→ ValueError(收缩守卫)。"""
    with pytest.raises(ValueError, match="2 的幂"):
        device_count_transform(_cfg(tp=4), {"device_count": 3})


def test_shrink_collapses_template_dp_to_one() -> None:
    """R-H:模板 TP>1 且 DP>1(TP=8/DP=2)、cnt=4<TP → 收缩 TP=4、**DP 塌到 1**(一份占 cnt 卡)。

    锁定"收缩取 TP=cnt、DP=1,不保留模板 DP"的语义(单机 40 个 TP>1/DP>1 recipe 命中此支;
    大模型由 resolve_config 前置显存闸拦截,docs/53)。
    """
    override, notes = device_count_transform(_cfg(tp=8, dp=2), {"device_count": 4})
    assert override == {"tensor_parallel_size": 4, "data_parallel_size": 1}
    assert notes["device_count_status"] == "tp_shrunk"


def test_cnt_not_multiple_of_m_raises() -> None:
    """cnt 非 M 整数倍(10%4≠0)→ ValueError(走公共核,不向下取整)。"""
    with pytest.raises(ValueError, match="整数倍"):
        device_count_transform(_cfg(tp=4), {"device_count": 10})


def test_tp_static_when_cnt_ge_tp() -> None:
    """cnt≥TP(够卡)时只动 DP;override 绝不含 tensor_parallel_size(TP 静态,R-A)。"""
    override, _ = device_count_transform(_cfg(tp=4, dp=4), {"device_count": 8})
    assert "tensor_parallel_size" not in override


def test_default_tp_one_when_absent() -> None:
    """模板无 TP → 缺省 M=1,DP=cnt(8)。"""
    override, notes = device_count_transform({"model": "m"}, {"device_count": 8})
    assert override == {"data_parallel_size": 8}
    assert notes["device_count_tp"] == "1"


def test_sglang_native_parallelism_keys_follow_device_count():
    override, notes = device_count_transform(
        {"model": "m", "tp_size": 16},
        {"device_count": 32, "engine": "sglang"},
    )

    assert override == {"dp_size": 2}
    assert notes["device_count_status"] == "overridden"
