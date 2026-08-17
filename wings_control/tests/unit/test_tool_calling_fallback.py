from pathlib import Path

from wings_ctl.core.config_resolver import _prepare_feature_context
from wings_ctl.loaders.locator import find_tool_calling_config


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_vllm_falls_back_to_other_quantization_variant(tmp_path):
    _write(
        tmp_path / "engines" / "vllm" / "hw" / "models" / "Qwen" / "qwen-fp8.yaml",
        """model:\n  name: Qwen3\n  variant_name: Qwen3-fp8\n  match:\n    - name_pattern: '(?i)qwen3'\nfeatures:\n  tool_calling:\n    args: [--enable-auto-tool-choice, --tool-call-parser, qwen3]\n""",
    )

    current = {"model": {"name": "Qwen3"}, "features": {}}
    features, _, _, source = _prepare_feature_context(
        tmp_path, "Qwen3-int4", "vllm", current, False, True
    )
    assert features["tool_calling"]["args"][-1] == "qwen3"
    assert source.endswith("qwen-fp8.yaml")


def test_vllm_ascend_falls_back_to_vllm_quantization_variant(tmp_path):
    _write(
        tmp_path / "engines" / "vllm" / "hw" / "models" / "Qwen3" / "qwen-fp8.yaml",
        """model:\n  name: Qwen3\n  variant_name: Qwen3-fp8\nfeatures:\n  tool_calling:\n    args: [--enable-auto-tool-choice, --tool-call-parser, qwen3]\n""",
    )
    current = {"model": {"name": "Qwen3"}, "features": {}}

    features, _, _, source = _prepare_feature_context(
        tmp_path, "Qwen3-w8a8", "vllm-ascend", current, False, True
    )
    assert features["tool_calling"]["args"][-1] == "qwen3"
    assert source.endswith("qwen-fp8.yaml")


def test_current_yaml_takes_precedence(tmp_path):
    current = {"features": {"tool_calling": {"args": ["--tool-call-parser", "local"]}}}
    features, _, _, _ = _prepare_feature_context(tmp_path, "Qwen3", "vllm", current, False, True)
    assert features["tool_calling"]["args"] == ["--tool-call-parser", "local"]


def test_canonical_model_name_scans_only_matching_model_directories(tmp_path):
    _write(
        tmp_path / "engines" / "vllm" / "hw-a" / "models" / "Qwen3" / "qwen.yaml",
        """model:\n  name: Qwen3\nfeatures:\n  tool_calling:\n    args: [--tool-call-parser, qwen3]\n""",
    )
    _write(
        tmp_path / "engines" / "vllm" / "hw-b" / "models" / "Other" / "other.yaml",
        """model:\n  name: Other\nfeatures:\n  tool_calling:\n    args: [--tool-call-parser, other]\n""",
    )

    data, path = find_tool_calling_config(
        tmp_path, "vllm", "Qwen3-int4", canonical_model_name="Qwen3"
    )
    assert path is not None and path.name == "qwen.yaml"
    assert data["features"]["tool_calling"]["args"][-1] == "qwen3"


def test_canonical_model_name_prevents_prefix_model_mismatch(tmp_path):
    _write(
        tmp_path / "engines" / "vllm" / "hw" / "models" / "DeepSeek-V3" / "v3.yaml",
        """model:\n  name: DeepSeek-V3\n  match:\n    - name_pattern: '(?i)deepseek[-.]?v3'\nfeatures:\n  tool_calling:\n    args: [--tool-call-parser, deepseek_v3]\n""",
    )
    _write(
        tmp_path / "engines" / "vllm" / "hw" / "models" / "DeepSeek-V3.2" / "v32.yaml",
        """model:\n  name: DeepSeek-V3.2\n  match:\n    - name_pattern: '(?i)deepseek[-.]?v3[.]2'\nfeatures:\n  tool_calling:\n    args: [--tool-call-parser, deepseek_v32]\n""",
    )

    data, path = find_tool_calling_config(
        tmp_path, "vllm", "DeepSeek-V3.2-w8a8", canonical_model_name="DeepSeek-V3.2"
    )
    assert path is not None and path.name == "v32.yaml"
    assert data["features"]["tool_calling"]["args"][-1] == "deepseek_v32"


def test_fallback_does_not_match_other_model(tmp_path):
    _write(
        tmp_path / "engines" / "vllm" / "hw" / "models" / "Llama" / "llama.yaml",
        """model:\n  name: Llama\n  match:\n    - name_pattern: '(?i)llama'\nfeatures:\n  tool_calling:\n    args: [--tool-call-parser, llama]\n""",
    )
    features, _, _, _ = _prepare_feature_context(tmp_path, "Qwen3", "vllm", {"features": {}}, False, True)
    assert "tool_calling" not in features


def test_fallback_only_applies_to_supported_engines(tmp_path):
    _write(
        tmp_path / "engines" / "sglang" / "hw" / "models" / "Qwen" / "qwen.yaml",
        "features:\n  tool_calling:\n    args: [--tool-call-parser, qwen3]\n",
    )
    assert find_tool_calling_config(tmp_path, "sglang", "Qwen3") == (None, None)


def test_disabled_switch_does_not_scan(tmp_path):
    features, _, _, _ = _prepare_feature_context(tmp_path, "Qwen3", "vllm", {"features": {}}, False, False)
    assert features == {}
