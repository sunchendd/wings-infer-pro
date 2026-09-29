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


def test_key_to_flag_preserves_nested_path_after_dot():
    """验证:只转换顶层参数;点号后的 vLLM 嵌套路径(含下划线)必须原样保留。"""
    assert (
        key_to_flag("kernel_config.enable_flashinfer_autotune")
        == "--kernel-config.enable_flashinfer_autotune"
    )


def test_flag_to_key_preserves_nested_path_after_dot():
    """验证:反向同样只转换顶层参数,点号后的嵌套路径原样保留。"""
    assert (
        flag_to_key("--kernel-config.enable_flashinfer_autotune")
        == "kernel_config.enable_flashinfer_autotune"
    )


def test_round_trip_underscore_keys():
    """验证:不含字面连字符的 key 可无损往返 key→flag→key。"""
    for key in ["max_model_len", "enable_auto_tool_choice", "tensor_parallel_size"]:
        assert flag_to_key(key_to_flag(key)) == key


def test_flag_to_key_without_prefix():
    """验证:无 -- 前缀时按主体原样处理(连字符转下划线),不误删字符。"""
    assert flag_to_key("max-model-len") == "max_model_len"


def test_render_param_tokens_uses_key_to_flag():
    """验证:顶层参数沿用现有 argv 规则,点号嵌套配置用单 token 赋值语法。"""
    assert render_param_tokens("max_model_len", 262144) == ["--max-model-len", "262144"]
    assert render_param_tokens("trust_remote_code", True) == ["--trust-remote-code"]
    assert render_param_tokens("trust_remote_code", False) is None
    assert render_param_tokens(
        "kernel_config.enable_flashinfer_autotune", False,
    ) == ["--kernel-config.enable_flashinfer_autotune=False"]


def test_render_param_tokens_expands_cudagraph_capture_sizes():
    """vLLM nargs 参数必须展开为多个 argv token，不能序列化成 JSON。"""
    assert render_param_tokens("cudagraph_capture_sizes", [1, 2, 4, 8]) == [
        "--cudagraph-capture-sizes",
        "1",
        "2",
        "4",
        "8",
    ]


def test_key_to_flag_cc_single_dash():
    """验证:vLLM 的 ``cc.*``(pass 配置)顶层前缀用**单横线** ``-cc.``,而非通用 ``--``。"""
    assert key_to_flag("cc.pass_config.fuse_allreduce_rms") == "-cc.pass_config.fuse_allreduce_rms"


def test_flag_to_key_cc_single_dash():
    """验证:单横线 ``-cc.`` flag 反解回 engine_config key(点号路径原样保留)。"""
    assert flag_to_key("-cc.pass_config.fuse_allreduce_rms") == "cc.pass_config.fuse_allreduce_rms"


def test_render_param_tokens_cc_single_dash():
    """验证:``cc.*`` 嵌套配置渲成单 token、单横线赋值(值含 bool False 也显式输出)。"""
    assert render_param_tokens("cc.pass_config.fuse_allreduce_rms", False) == [
        "-cc.pass_config.fuse_allreduce_rms=False"
    ]


def test_parse_feature_args_uses_flag_to_key():
    """验证:消费方 feature_overlay 反解仍得原 key(委托 helper 后行为不变)。"""
    out = parse_feature_args(["--enable-auto-tool-choice", "--tool-call-parser", "glm45"])
    assert out == {"enable_auto_tool_choice": True, "tool_call_parser": "glm45"}
