"""custom_features expander 单测 — 自由启动参数(always-on,深合并)。"""

from wings_accel.custom import smart_custom_features_expander
from wings_accel.render import PlaceholderContext


def test_custom_empty_returns_none():
    assert smart_custom_features_expander(None, PlaceholderContext()) is None
    assert smart_custom_features_expander([], PlaceholderContext()) is None


def test_custom_single_bool_flag():
    block = [{"name": "Mamba prefix caching", "cli_params": {"mamba_cache": True}}]
    out = smart_custom_features_expander(block, PlaceholderContext())
    assert out is not None
    assert out.scheme == "Mamba prefix caching"
    assert out.engine_params.engine_config["mamba_cache"] is True


def test_custom_multiple_merged():
    block = [
        {"name": "A", "cli_params": {"trust_remote_code": True}, "envs": {"A": "1"}},
        {"name": "B", "cli_params": {"kv_cache_dtype": "fp8"}, "envs": {"B": "2"}},
    ]
    out = smart_custom_features_expander(block, PlaceholderContext())
    cfg = out.engine_params.engine_config
    assert cfg["trust_remote_code"] is True
    assert cfg["kv_cache_dtype"] == "fp8"
    assert out.engine_params.env == {"A": "1", "B": "2"}


def test_custom_envs_only():
    block = [{"name": "Ears", "cli_params": {}, "envs": {"EARS_TOLERANCE": "0.3"}}]
    out = smart_custom_features_expander(block, PlaceholderContext())
    assert out.engine_params.env == {"EARS_TOLERANCE": "0.3"}


def test_custom_placeholder_path():
    """$path 令牌在 custom cli_params 内也能解析。"""
    block = [{"name": "X", "cli_params": {"foo": "$path"}}]
    out = smart_custom_features_expander(block, PlaceholderContext(draft_model_path="/draft/m"))
    assert out.engine_params.engine_config == {"foo": "/draft/m"}
