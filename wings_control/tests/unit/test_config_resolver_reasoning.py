from __future__ import annotations

from pathlib import Path

from wings_ctl.core import config_resolver
from wings_ctl.loaders.reasoning_table import LoadedReasoningTable
from wings_ctl.strategy.reasoning_resolver import ReasoningResolution, ReasoningSpec


def test_model_yaml_reasoning_takes_precedence(monkeypatch) -> None:
    loaded = LoadedReasoningTable({"architectures": []}, "/public/reason_parser.yaml")
    resolve_called = False

    def fail_resolve(*args, **kwargs):
        nonlocal resolve_called
        resolve_called = True
        raise AssertionError("public table must not override model YAML reasoning")

    monkeypatch.setattr(config_resolver, "load_reasoning_table", lambda _: loaded)
    monkeypatch.setattr(config_resolver, "resolve_reasoning", fail_resolve)

    features, result, source = config_resolver._prepare_feature_context(
        Path("/config"),
        "Qwen3",
        "vllm",
        {
            "features": {
                "reasoning": {"args": ["--reasoning-parser", "local_parser"]},
                "tool_calling": {"args": ["--tool-call-parser", "qwen3"]},
            },
        },
        True,
    )

    assert features["reasoning"] == {"args": ["--reasoning-parser", "local_parser"]}
    assert features["tool_calling"]["args"] == ["--tool-call-parser", "qwen3"]
    assert result is None
    assert source == ""
    assert not resolve_called


def test_public_table_is_used_when_model_yaml_has_no_reasoning(monkeypatch) -> None:
    loaded = LoadedReasoningTable({"architectures": []}, "/public/reason_parser.yaml")
    resolution = ReasoningResolution(
        "matched",
        ReasoningSpec(
            ("--reasoning-parser", "public_parser"),
            "architectures[0].models.Qwen3.vllm",
        ),
        loaded.source_path,
        "model",
    )
    monkeypatch.setattr(config_resolver, "load_reasoning_table", lambda _: loaded)
    monkeypatch.setattr(config_resolver, "resolve_reasoning", lambda *args, **kwargs: resolution)

    features, result, source = config_resolver._prepare_feature_context(
        Path("/config"),
        "Qwen3",
        "vllm",
        {"features": {"tool_calling": {"args": ["--tool-call-parser", "qwen3"]}}},
        True,
    )

    assert features["reasoning"] == {"args": ["--reasoning-parser", "public_parser"]}
    assert features["tool_calling"]["args"] == ["--tool-call-parser", "qwen3"]
    assert result is resolution
    assert source == loaded.source_path


def test_reasoning_feature_is_not_loaded_when_switch_is_disabled(monkeypatch) -> None:
    def fail_load(_):
        raise AssertionError("public reasoning table must not be loaded")

    monkeypatch.setattr(config_resolver, "load_reasoning_table", fail_load)
    features, result, source = config_resolver._prepare_feature_context(
        Path("/config"),
        "Qwen3",
        "vllm",
        {"features": {"reasoning": {"args": ["--reasoning-parser", "local_parser"]}}},
        False,
    )

    assert features["reasoning"] == {"args": ["--reasoning-parser", "local_parser"]}
    assert result is None
    assert source == ""
