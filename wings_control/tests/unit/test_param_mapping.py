from __future__ import annotations

from wings_ctl.translators.cli_translator import CLITranslator
from wings_ctl.translators.cli_translator import filter_maas_contract_overrides
from wings_ctl.translators.param_mapping import (
    MAAS_CONTRACT_ALLOWLIST,
    drop_reason,
    translate,
)


def test_translate_rename_keys():
    assert translate("model_path", "vllm") == "model"
    assert translate("model_name", "vllm") == "served_model_name"


def test_translate_passthrough_keys():
    assert translate("host", "vllm") == "host"
    assert translate("max_num_seqs", "vllm") == "max_num_seqs"


_OPEN_PARAMS = ("seed", "dtype", "kv_cache_dtype", "quantization", "quantization_param_path",
                "gpu_memory_utilization", "block_size", "enable_chunked_prefill",
                "enable_prefix_caching", "enable_expert_parallel")


def test_translate_open_params_passthrough():
    """评审定:原"不覆盖基线"一组改同名直通(user_cli 最高,覆盖 recipe)。"""
    for key in _OPEN_PARAMS:
        assert translate(key, "vllm") == key          # 同名直通,不再 drop
        assert drop_reason(key, "vllm") is None


def test_open_params_passthrough_ascend():
    """验证 vllm-ascend 共用 _VLLM:开源参数同名直通、不丢弃。

    注:sglang 自 docs/49 起有独立 _SGLANG 映射(部分改名/丢弃),不再走"默认直通",
    其翻译由 tests/unit/test_sglang_render.py 单独覆盖。
    """
    for key in _OPEN_PARAMS:
        assert translate(key, "vllm-ascend") == key, f"vllm-ascend:{key} 应直通"
        assert drop_reason(key, "vllm-ascend") is None, f"vllm-ascend:{key} 不应有 drop reason"


def test_translate_drop_keys():
    """仍丢弃:input/output_length(vllm 无对应)、enable_auto_think_choice(Step3.2)。"""
    assert translate("input_length", "vllm") is None
    assert translate("output_length", "vllm") is None
    assert translate("enable_auto_think_choice", "vllm") is None
    assert drop_reason("input_length", "vllm") is not None


def test_translate_unknown_engine_passthrough():
    """未注册引擎 → 缺省同名直通。"""
    assert translate("model_path", "some-new-engine") == "model_path"


def test_translate_mindie_uses_extension_mapping():
    """已注册的 MindIE 引擎使用扩展参数映射。"""
    assert translate("model_path", "mindie") == "model"


def test_maas_contract_allowlist_excludes_quant_and_caching_keys():
    assert "quantization" not in MAAS_CONTRACT_ALLOWLIST
    assert "enable_prefix_caching" not in MAAS_CONTRACT_ALLOWLIST
    assert "enable_expert_parallel" not in MAAS_CONTRACT_ALLOWLIST


def test_filter_maas_contract_overrides_drops_non_contract_keys_with_reason():
    allowed, dropped = filter_maas_contract_overrides(
        {
            "model_path": "/m",
            "quantization": "fp8",
            "enable_prefix_caching": True,
            "enable_expert_parallel": True,
        }
    )
    assert allowed == {"model_path": "/m"}
    dropped_keys = {row["key"] for row in dropped}
    assert dropped_keys == {"quantization", "enable_prefix_caching", "enable_expert_parallel"}
    assert all(row["reason"] == "maas_status=not_in_maas_contract_allowlist" for row in dropped)


def test_translate_vllm_and_vllm_ascend_consistent():
    sample_keys = [
        "model_path",
        "model_name",
        "seed",
        "input_length",
        "host",
        "max_num_seqs",
    ]
    for key in sample_keys:
        assert translate(key, "vllm") == translate(key, "vllm-ascend")


def test_cli_translator_translates_and_collects_dropped():
    translated, dropped = CLITranslator.translate_overrides(
        {
            "model_path": "/m",
            "model_name": "X",
            "seed": 42,                # 现在直通(user_cli 覆盖 recipe)
            "input_length": 4096,      # 仍丢弃(vllm 无对应)
            "host": "0.0.0.0",
        },
        "vllm",
    )

    assert translated == {"model": "/m", "served_model_name": "X", "seed": 42, "host": "0.0.0.0"}
    assert any(item["key"] == "input_length" and "reason" in item for item in dropped)
    assert all(item["key"] != "seed" for item in dropped)   # seed 不再被丢


def test_cli_translator_warns_for_enable_auto_think_choice(caplog):
    with caplog.at_level("WARNING"):
        translated, dropped = CLITranslator.translate_overrides(
            {"enable_auto_think_choice": True},
            "vllm",
        )
    assert not translated
    assert dropped[0]["key"] == "enable_auto_think_choice"
    # 警告文案更新为准确口径:不直通、由 FeatureOverlay reasoning gate 接管(不再说"暂未实现")。
    assert "FeatureOverlay" in caplog.text and "reasoning" in caplog.text
