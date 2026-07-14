"""FeatureOverlay 小策略层单测(Step 3.2)。

对应实现 src/wings_ctl/strategy/feature_overlay.py。覆盖:B1 args 反解、开关→特性查表、
spec_decoding 不归本层、无 features 块 no-op、开关开但缺特性 warn-skip。
"""

from __future__ import annotations

from wings_ctl.strategy.feature_overlay import (
    feature_overlay_transform,
    parse_feature_args,
)


# ── parse_feature_args(B1 反解)────────────────────────────────────────────

def test_parse_kv_and_bare_flag() -> None:
    """验证 kv(--flag value)反解成 key=value、裸 flag 反解成 key=True。"""
    parsed = parse_feature_args(["--enable-auto-tool-choice", "--tool-call-parser", "glm45"])
    assert parsed == {"enable_auto_tool_choice": True, "tool_call_parser": "glm45"}


def test_parse_order_independent_bare_last() -> None:
    """验证 flag 顺序不固定:裸 flag 在末尾也能识别为 True(qwen 风格)。"""
    parsed = parse_feature_args(["--tool-call-parser", "qwen3_coder", "--enable-auto-tool-choice"])
    assert parsed == {"tool_call_parser": "qwen3_coder", "enable_auto_tool_choice": True}


def test_parse_extra_chat_template() -> None:
    """验证带 --chat-template 的 args(gemma4 风格)也能正确反解出该 kv。"""
    parsed = parse_feature_args(
        ["--enable-auto-tool-choice", "--tool-call-parser", "gemma4", "--chat-template", "x.jinja"]
    )
    assert parsed["chat_template"] == "x.jinja"
    assert parsed["tool_call_parser"] == "gemma4"


def test_parse_empty_returns_empty() -> None:
    """验证空 args / None → 空 dict。"""
    assert not parse_feature_args([])
    assert not parse_feature_args(None)  # type: ignore[arg-type]


# ── feature_overlay_transform ──────────────────────────────────────────────

_FEATURES = {
    "tool_calling": {"args": ["--tool-call-parser", "glm45", "--enable-auto-tool-choice"]},
    "reasoning": {"args": ["--reasoning-parser", "glm45"]},
    "spec_decoding": {"args": ["--speculative-config.method", "mtp"]},
}


def test_overlay_tool_switch_on() -> None:
    """验证开 tool 开关 → 附加 tool_calling 的完整 args(parser + flag)。"""
    override, notes = feature_overlay_transform(
        {}, {"features": _FEATURES, "feature_switches": {"enable_auto_tool_choice": True}}
    )
    assert override == {"tool_call_parser": "glm45", "enable_auto_tool_choice": True}
    assert notes["feature_overlay.tool_calling"].startswith("applied")


def test_overlay_reasoning_switch_on() -> None:
    """验证开 think 开关 → 附加 reasoning 的 --reasoning-parser。"""
    override, _ = feature_overlay_transform(
        {}, {"features": _FEATURES, "feature_switches": {"enable_auto_think_choice": True}}
    )
    assert override == {"reasoning_parser": "glm45"}


def test_overlay_both_switches() -> None:
    """验证 tool + think 同开 → 两特性 args 合并。"""
    override, _ = feature_overlay_transform(
        {},
        {
            "features": _FEATURES,
            "feature_switches": {"enable_auto_tool_choice": True, "enable_auto_think_choice": True},
        },
    )
    assert override["tool_call_parser"] == "glm45"
    assert override["reasoning_parser"] == "glm45"


def test_overlay_no_switch_is_noop() -> None:
    """验证无开关 → no-op(特性默认随 model.yaml,D2)。"""
    override, notes = feature_overlay_transform({}, {"features": _FEATURES, "feature_switches": {}})
    assert not override
    assert not notes


def test_overlay_no_features_block_is_noop() -> None:
    """验证无 features 块(如未迁移 ascend)+ 开关开 → warn-skip,不 raise、不附加。"""
    override, notes = feature_overlay_transform(
        {}, {"feature_switches": {"enable_auto_tool_choice": True}}
    )
    assert not override
    assert "switch_on_but_absent" in notes["feature_overlay.tool_calling"]


def test_overlay_spec_decoding_not_handled() -> None:
    """验证 spec_decoding 不归本层:即便 features 有它,也不会被附加(转 wings-accel)。"""
    override, notes = feature_overlay_transform(
        {},
        {
            "features": _FEATURES,
            # 没有 spec 对应的开关键进 _SWITCH_TO_FEATURE,故任何开关都不触发 spec
            "feature_switches": {"enable_auto_tool_choice": True},
        },
    )
    assert "speculative_config" not in override
    assert "method" not in override
    assert "feature_overlay.spec_decoding" not in notes
