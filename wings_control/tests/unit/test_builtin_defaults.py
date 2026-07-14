"""builtin_default 层(最低优先级 host/port 兜底)单测。

验证三种情形:模板/用户都缺 → builtin 兜底;模板有 → 模板覆盖 builtin;
用户传 → user_cli 覆盖一切。对应 config_resolver._BUILTIN_DEFAULTS + trace_merge 层序。
"""

from __future__ import annotations

from wings_ctl.core.config_resolver import _BUILTIN_DEFAULTS, MergeLayer, trace_merge


def _merge(scenario: dict, user: dict):
    """按真实层序合并:builtin_default → model_scenario → user_cli,返回 traces。"""
    return trace_merge([
        MergeLayer("builtin_default", _BUILTIN_DEFAULTS, "<builtin_default>", "builtin_default"),
        MergeLayer("model_scenario", scenario, "f.yaml", "scenarios"),
        MergeLayer("user_cli", user, "<user_cli>", "user_cli"),
    ])


def test_builtin_default_constant() -> None:
    """常量值锁定:host=0.0.0.0 / port=17000(proxy 迁移:engine 监听 backend 端口 17000)。"""
    assert _BUILTIN_DEFAULTS == {"host": "0.0.0.0", "port": 17000}


def test_builtin_fills_when_template_and_user_absent() -> None:
    """模板与用户都没给 → host/port 由 builtin 兜底,final_layer=builtin_default。"""
    traces = _merge({}, {})
    assert traces["host"].final_value == "0.0.0.0"
    assert traces["host"].final_layer == "builtin_default"
    assert traces["port"].final_value == 17000
    assert traces["port"].final_layer == "builtin_default"


def test_template_overrides_builtin() -> None:
    """模板给了 port → 覆盖 builtin(final_layer=model_scenario);host 仍由 builtin 兜底。"""
    traces = _merge({"port": 8008}, {})
    assert traces["port"].final_value == 8008
    assert traces["port"].final_layer == "model_scenario"
    assert traces["host"].final_value == "0.0.0.0"
    assert traces["host"].final_layer == "builtin_default"


def test_user_overrides_builtin_and_template() -> None:
    """用户传 host/port → 最高优先级覆盖 builtin 与模板(final_layer=user_cli)。"""
    traces = _merge({"port": 8008}, {"port": 9999, "host": "127.0.0.1"})
    assert traces["port"].final_value == 9999
    assert traces["port"].final_layer == "user_cli"
    assert traces["host"].final_value == "127.0.0.1"
    assert traces["host"].final_layer == "user_cli"
