from wings_accel.decoders import smart_decoding_expander
from wings_accel.render import PlaceholderContext
from wings_accel.schemas import ModelConfig, SmartDecodingConfig


def make_ctx(draft=""):
    return PlaceholderContext(draft_model_path=draft)


def make_input(enabled, model_path="", model_arch=""):
    return (
        SmartDecodingConfig(enabled=enabled, model_path=model_path),
        ModelConfig(model_path="/models/llama", model_arch=model_arch),
    )


def make_decoding_block():
    """new:list 形式,speculative_config 在 cli_params 下。"""
    return [
        {
            "name": "eagle3",
            "requires_model_path": True,
            "cli_params": {
                "speculative_config": {
                    "method": "eagle3",
                    "num_speculative_tokens": 3,
                    "model": "$path",
                },
                "enforce_eager": True,  # bool → 裸 flag --enforce-eager
            },
            "envs": {"EARS_TOLERANCE": "0.3"},
        },
        {
            "name": "mtp",
            "priority": 1,
            "cli_params": {"speculative_config": {"method": "mtp", "num_speculative_tokens": 1}},
            "envs": {},
        },
    ]


def test_decoding_enabled_false():
    cfg, mod = make_input(enabled=False)
    assert smart_decoding_expander(cfg, mod, None, make_ctx()) is None


def test_decoding_model_based_hit():
    cfg, mod = make_input(enabled=True, model_path="/draft/eagle", model_arch="EAGLE3-LLaMA")
    out = smart_decoding_expander(cfg, mod, make_decoding_block(), make_ctx("/draft/eagle"))
    assert out.scheme == "eagle3"
    assert out.degraded is False
    assert out.engine_params.engine_config["speculative_config"]["method"] == "eagle3"
    assert out.engine_params.engine_config["speculative_config"]["model"] == "/draft/eagle"
    assert out.engine_params.engine_config["enforce_eager"] is True
    # envs
    assert out.engine_params.env == {"EARS_TOLERANCE": "0.3"}


def test_decoding_model_based_miss_degrade_to_no_model():
    block = [{"name": "mtp", "priority": 1, "cli_params": {"speculative_config": {"method": "mtp"}}}]
    cfg, mod = make_input(enabled=True, model_path="/draft/unknown", model_arch="UnknownArch")
    out = smart_decoding_expander(cfg, mod, block, make_ctx("/draft/unknown"))
    assert out.scheme == "mtp"
    assert out.degraded is True
    assert "model_based_miss->no_model" in out.degrade_reason


def test_decoding_no_model_hit():
    cfg, mod = make_input(enabled=True, model_path="", model_arch="")
    out = smart_decoding_expander(cfg, mod, make_decoding_block(), make_ctx())
    assert out.scheme == "mtp"
    assert out.degraded is False


def test_decoding_requires_model_path_gate():
    """requires_model_path 的方案在无草稿路径时不可选 → 回落 no_model。"""
    block = [
        {"name": "eagle3", "requires_model_path": True,
         "cli_params": {"speculative_config": {"method": "eagle3"}}},
        {"name": "mtp", "priority": 1, "cli_params": {"speculative_config": {"method": "mtp"}}},
    ]
    # 无 model_path 时 model_based 完全跳过
    cfg, mod = make_input(enabled=True, model_path="", model_arch="eagle")
    out = smart_decoding_expander(cfg, mod, block, make_ctx())
    assert out.scheme == "mtp"  # eagle3 因 requires_model_path 被门挡住


def test_decoding_no_method_match_fallback():
    cfg, mod = make_input(enabled=True)
    assert smart_decoding_expander(cfg, mod, [], make_ctx()) is None


def test_decoding_missing_block_disabled():
    cfg, mod = make_input(enabled=True)
    assert smart_decoding_expander(cfg, mod, None, make_ctx()) is None


def test_decoding_pd_prefill_disabled():
    cfg, mod = make_input(enabled=True, model_path="/draft/eagle", model_arch="EAGLE3")
    out = smart_decoding_expander(cfg, mod, make_decoding_block(), make_ctx("/draft/eagle"), pd_role="prefill")
    assert out is None


def test_decoding_pd_decode_normal():
    cfg, mod = make_input(enabled=True, model_path="/draft/eagle", model_arch="EAGLE3")
    out = smart_decoding_expander(cfg, mod, make_decoding_block(), make_ctx("/draft/eagle"), pd_role="decode")
    assert out.scheme == "eagle3"
