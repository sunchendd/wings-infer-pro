"""env→bool 统一解析回归测试。

覆盖 backlog P0(env→bool 三套不一致)统一后的口径:
`env_utils.parse_bool` / `env_utils.env_bool` 为单一判定点,
`noise_filter._env_bool` 与 `accel/smart_accel._as_bool` 均委托它。
重点锁定"smart_accel 只认 'true' 导致 ENABLE_XXX=1/yes 不生效"这一 bug 已修。
"""

from __future__ import annotations

import logging

import pytest

from wings_ctl.accel.smart_accel import _as_bool
from wings_ctl.utils.env_utils import env_bool, parse_bool


@pytest.mark.parametrize("raw", ["1", "true", "True", "TRUE", "yes", "Yes", "y", "on", "ON", "  on  "])
def test_parse_bool_true_values(raw):
    """验证:真值集合(含大小写/前后空格变体)→ True,与 default 无关。"""
    assert parse_bool(raw, default=False) is True
    assert parse_bool(raw, default=True) is True


@pytest.mark.parametrize("raw", ["0", "false", "False", "FALSE", "no", "No", "n", "off", "OFF", "  off "])
def test_parse_bool_false_values(raw):
    """验证:假值集合(含大小写/前后空格变体)→ False,与 default 无关。"""
    assert parse_bool(raw, default=True) is False
    assert parse_bool(raw, default=False) is False


def test_parse_bool_unset_returns_default():
    """验证:None(未设置)→ 原样返回 default(两个方向都要对)。"""
    assert parse_bool(None, default=True) is True
    assert parse_bool(None, default=False) is False


@pytest.mark.parametrize("raw", ["", "   ", "\t"])
def test_parse_bool_empty_returns_default(raw):
    """验证:空串 / 纯空白 → 返回 default。"""
    assert parse_bool(raw, default=True) is True
    assert parse_bool(raw, default=False) is False


def test_parse_bool_invalid_warns_and_returns_default(caplog):
    """验证:非法值 → 打 WARNING 且返回 default(不静默、不误判)。"""
    with caplog.at_level(logging.WARNING):
        assert parse_bool("banana", default=True) is True
        assert parse_bool("banana", default=False) is False
    assert any("非法布尔值" in r.message for r in caplog.records)


def test_env_bool_reads_environment(monkeypatch):
    """验证:env_bool 从环境变量读取并按 parse_bool 解析;未设置回 default。"""
    monkeypatch.setenv("WINGS_TEST_FLAG", "yes")
    assert env_bool("WINGS_TEST_FLAG", default=False) is True
    monkeypatch.setenv("WINGS_TEST_FLAG", "off")
    assert env_bool("WINGS_TEST_FLAG", default=True) is False
    monkeypatch.delenv("WINGS_TEST_FLAG", raising=False)
    assert env_bool("WINGS_TEST_FLAG", default=True) is True
    assert env_bool("WINGS_TEST_FLAG", default=False) is False


@pytest.mark.parametrize("val", ["1", "yes", "on", "true", "Y"])
def test_smart_accel_as_bool_enabled_for_truthy(val):
    """验证:回归 bug —— smart_accel 对 ENABLE_XXX=1/yes/on 等真值应启用(此前只认 'true')。"""
    assert _as_bool({"ENABLE_XXX": val}, "ENABLE_XXX") is True


@pytest.mark.parametrize("val", ["0", "no", "off", "false"])
def test_smart_accel_as_bool_disabled_for_falsy(val):
    """验证:smart_accel 对 ENABLE_XXX 假值 → 关闭。"""
    assert _as_bool({"ENABLE_XXX": val}, "ENABLE_XXX") is False


def test_smart_accel_as_bool_missing_key_defaults_false():
    """验证:MaaS env 缺该开关键 → 默认 False(默认语义保持不变)。"""
    assert _as_bool({}, "ENABLE_XXX") is False
