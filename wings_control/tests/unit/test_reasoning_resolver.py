from wings_ctl.strategy.reasoning_resolver import (
    ModelIdentity,
    build_model_identity,
    resolve_reasoning,
)


def table():
    return {
        "architectures": [
            {
                "name": "Qwen3ForCausalLM",
                "config": {"vllm": {"default": "qwen3"}},
                "models": {
                    "Qwen3-32B": {"vllm": "qwen3"},
                    "Qwen3-Coder": {"vllm": None},
                    "DeepSeek-R1": {"vllm": "deepseek_r1"},
                },
            }
        ]
    }


def test_build_model_identity_reads_variant_name():
    identity = build_model_identity(
        "DeepSeek.R1",
        {"model": {"variant_name": "DeepSeek-R1"}},
    )
    assert identity.requested_name == "DeepSeek.R1"
    assert identity.variant_name == "DeepSeek-R1"


def test_variant_name_matches_public_table_for_alias():
    result = resolve_reasoning(
        table(),
        ModelIdentity("DeepSeek.R1", variant_name="DeepSeek-R1"),
        "vllm",
    )
    assert result.status == "matched"
    assert result.spec.args == ("--reasoning-parser", "deepseek_r1")


def test_exact_model_match_is_case_insensitive():
    result = resolve_reasoning(table(), ModelIdentity("qwen3-32b"), "vllm")
    assert result.status == "matched"
    assert result.spec.args == ("--reasoning-parser", "qwen3")
    assert result.spec.source == "architectures[0].models.Qwen3-32B.vllm"


def test_null_means_no_exact_match():
    result = resolve_reasoning(table(), ModelIdentity("QWEN3-CODER"), "vllm")
    assert result.status == "unmatched"
    assert result.spec is None


def test_unmatched_does_not_fallback():
    result = resolve_reasoning(table(), ModelIdentity("unknown"), "vllm")
    assert result.status == "unmatched"
    assert result.spec is None


def test_architecture_default_is_not_used():
    result = resolve_reasoning(table(), ModelIdentity("unknown"), "vllm")
    assert result.status == "unmatched"
