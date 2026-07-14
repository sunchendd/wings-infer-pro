"""key/flag 名称转换 helper 单测(backlog #4:收口两处重复 replace)。

锁定 key_to_flag / flag_to_key 与旧内联 `.replace` 行为完全一致,
并验证 vllm_adapter / feature_overlay 两处消费方仍按原规则工作(零 argv 变化)。
"""

from __future__ import annotations

from wings_ctl.engines.param_names import flag_to_key, key_to_flag
from wings_ctl.engines.vllm_adapter import render_param_tokens
from wings_ctl.strategy.feature_overlay import parse_feature_args


def test_key_to_flag_basic():
    """验证:下划线 key → --连字符 flag。"""
    assert key_to_flag("max_model_len") == "--max-model-len"
    assert key_to_flag("enable_auto_tool_choice") == "--enable-auto-tool-choice"


def test_flag_to_key_basic():
    """验证:--连字符 flag → 下划线 key。"""
    assert flag_to_key("--max-model-len") == "max_model_len"
    assert flag_to_key("--enable-auto-tool-choice") == "enable_auto_tool_choice"


def test_key_to_flag_preserves_dot():
    """验证:点号参数只转下划线、不动点号(锁定当前真实行为)。"""
    assert (
        key_to_flag("attention_config.use_fp4_indexer_cache")
        == "--attention-config.use-fp4-indexer-cache"
    )


def test_flag_to_key_preserves_dot():
    """验证:反向同样保留点号,连字符转回下划线。"""
    assert (
        flag_to_key("--attention-config.use-fp4-indexer-cache")
        == "attention_config.use_fp4_indexer_cache"
    )


def test_round_trip_underscore_keys():
    """验证:不含字面连字符的 key 可无损往返 key→flag→key。"""
    for key in ["max_model_len", "enable_auto_tool_choice", "tensor_parallel_size"]:
        assert flag_to_key(key_to_flag(key)) == key


def test_flag_to_key_without_prefix():
    """验证:无 -- 前缀时按主体原样处理(连字符转下划线),不误删字符。"""
    assert flag_to_key("max-model-len") == "max_model_len"


def test_render_param_tokens_uses_key_to_flag():
    """验证:消费方 vllm_adapter 渲染仍产出原 argv(委托 helper 后行为不变)。"""
    assert render_param_tokens("max_model_len", 262144) == ["--max-model-len", "262144"]
    assert render_param_tokens("trust_remote_code", True) == ["--trust-remote-code"]
    assert render_param_tokens("trust_remote_code", False) is None


def test_parse_feature_args_uses_flag_to_key():
    """验证:消费方 feature_overlay 反解仍得原 key(委托 helper 后行为不变)。"""
    out = parse_feature_args(["--enable-auto-tool-choice", "--tool-call-parser", "glm45"])
    assert out == {"enable_auto_tool_choice": True, "tool_call_parser": "glm45"}
