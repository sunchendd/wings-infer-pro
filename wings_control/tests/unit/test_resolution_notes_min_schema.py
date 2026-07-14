from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from wings_ctl import __version__ as wings_ctl_version
from wings_ctl.core import config_resolver
from wings_ctl.core.config_resolver import resolve_config
from wings_ctl.core.models import (
    EngineVersion,
    HardwareContext,
    ResolvedEnv,
    Target,
)
from wings_ctl.core.topology import Topology


def _make_model_data(
    *,
    min_engine_version: str | None,
    schema_version: str | None,
) -> Dict[str, Any]:
    model_block: Dict[str, Any] = {
        "name": "unit-test-model",
        "match": [{"name_pattern": "(?i)unit-test-model"}],
    }
    if min_engine_version is not None:
        model_block["min_engine_version"] = min_engine_version

    data: Dict[str, Any] = {
        "model": model_block,
        "scenarios": {
            "standalone": {
                "engine_config": {"model": "acme/unit-test-model"},
                "env": {},
            }
        },
    }
    if schema_version is not None:
        data["schema_version"] = schema_version
    return data


def _patch_loader_outputs(
    monkeypatch,
    *,
    model_data: Dict[str, Any],
    platform_data: Dict[str, Any],
) -> None:
    monkeypatch.setattr(
        config_resolver,
        "load_platform_config",
        lambda *args, **kwargs: (platform_data, Path("/tmp/default_model.yaml")),
    )
    monkeypatch.setattr(
        config_resolver,
        "load_model_config",
        lambda *args, **kwargs: (model_data, Path("/tmp/model.yaml"), "(?i)unit-test-model"),
    )
    # resolve_family_dir 也是目录定位(真实文件系统);mock loaders 时一并 mock:原样返回下发 family。
    monkeypatch.setattr(
        config_resolver,
        "resolve_family_dir",
        lambda *args, **kwargs: args[2],  # (config_root, engine, hardware_family, ...)
    )


def _make_engine_version(
    *,
    requested: str | None,
    resolved: str | None = None,
    has_version_dir: bool = False,
) -> EngineVersion:
    return EngineVersion(
        requested=requested,
        resolved=resolved if resolved is not None else (requested or ""),
        is_fallback=False,
        has_version_dir=has_version_dir,
    )


def test_min_engine_version_warn_and_schema_versions_present(monkeypatch, caplog):
    model_data = _make_model_data(min_engine_version="0.20.0", schema_version="2.0.0")
    platform_data = {"schema_version": "1.0.0"}
    _patch_loader_outputs(monkeypatch, model_data=model_data, platform_data=platform_data)

    with caplog.at_level(logging.WARNING):
        resolved = resolve_config(
            ResolvedEnv(
                config_root=Path("/tmp/config"),
                hardware=HardwareContext("h100", "nvidia", {}),
                engine_version=_make_engine_version(requested="0.19.0"),
            ),
            Target(model_name="unit-test-model", topology=Topology.STANDALONE, engine="vllm"),
        )

    notes = resolved.resolution_notes
    assert notes["min_engine_version"] == "0.20.0"
    assert notes["engine_version_for_min_check"] == "0.19.0"
    assert notes["engine_version_for_min_check_source"] == "resolved"
    assert notes["min_engine_version_check"] == "warn"
    assert notes["min_engine_version_check_reason"] == "engine_version_below_min"
    assert notes["model_schema_version"] == "2.0.0"
    assert notes["default_model_schema_version"] == "1.0.0"
    assert notes["wings_ctl_version"] == wings_ctl_version
    msg = "Engine version=0.19.0 used for min-check is lower than model.min_engine_version=0.20.0"
    assert any(msg in r.message for r in caplog.records)


def test_min_engine_version_pass_when_engine_meets_min(monkeypatch, caplog):
    model_data = _make_model_data(min_engine_version="v0.20.0", schema_version="2.0.0")
    platform_data = {"schema_version": "1.0.0"}
    _patch_loader_outputs(monkeypatch, model_data=model_data, platform_data=platform_data)

    with caplog.at_level(logging.WARNING):
        resolved = resolve_config(
            ResolvedEnv(
                config_root=Path("/tmp/config"),
                hardware=HardwareContext("h100", "nvidia", {}),
                engine_version=_make_engine_version(requested="0.20.0"),
            ),
            Target(model_name="unit-test-model", topology=Topology.STANDALONE, engine="vllm"),
        )

    notes = resolved.resolution_notes
    assert notes["min_engine_version"] == "v0.20.0"
    assert notes["engine_version_for_min_check"] == "0.20.0"
    assert notes["engine_version_for_min_check_source"] == "resolved"
    assert notes["min_engine_version_check"] == "pass"
    assert notes["min_engine_version_check_reason"] == "engine_version_meets_min"
    assert not any("model.min_engine_version" in r.message for r in caplog.records)


def test_min_engine_version_skip_when_field_missing_and_schema_unset(monkeypatch, caplog):
    model_data = _make_model_data(min_engine_version=None, schema_version=None)
    platform_data: Dict[str, Any] = {}
    _patch_loader_outputs(monkeypatch, model_data=model_data, platform_data=platform_data)

    with caplog.at_level(logging.WARNING):
        resolved = resolve_config(
            ResolvedEnv(
                config_root=Path("/tmp/config"),
                hardware=HardwareContext("h100", "nvidia", {}),
                engine_version=_make_engine_version(requested="0.19.0"),
            ),
            Target(model_name="unit-test-model", topology=Topology.STANDALONE, engine="vllm"),
        )

    notes = resolved.resolution_notes
    assert notes["min_engine_version"] == "unset"
    assert notes["engine_version_for_min_check"] == "0.19.0"
    assert notes["engine_version_for_min_check_source"] == "resolved"
    assert notes["min_engine_version_check"] == "skip"
    assert notes["min_engine_version_check_reason"] == "min_engine_version_unset"
    assert notes["model_schema_version"] == "unset"
    assert notes["default_model_schema_version"] == "unset"
    assert notes["wings_ctl_version"] == wings_ctl_version
    assert not any("min_engine_version" in r.message for r in caplog.records)


def test_min_engine_version_uses_resolved_version_on_latest_fallback(monkeypatch, caplog):
    model_data = _make_model_data(min_engine_version="0.19.0", schema_version=None)
    platform_data: Dict[str, Any] = {}
    _patch_loader_outputs(monkeypatch, model_data=model_data, platform_data=platform_data)

    with caplog.at_level(logging.WARNING):
        resolved = resolve_config(
            ResolvedEnv(
                config_root=Path("/tmp/config"),
                hardware=HardwareContext("h100", "nvidia", {}),
                engine_version=_make_engine_version(
                    requested="0.20.0",
                    resolved="0.18.0",
                    has_version_dir=True,
                ),
            ),
            Target(model_name="unit-test-model", topology=Topology.STANDALONE, engine="vllm"),
        )

    notes = resolved.resolution_notes
    assert notes["min_engine_version"] == "0.19.0"
    assert notes["engine_version_for_min_check"] == "0.18.0"
    assert notes["engine_version_for_min_check_source"] == "resolved"
    assert notes["min_engine_version_check"] == "warn"
    assert notes["min_engine_version_check_reason"] == "engine_version_below_min"
    msg = "Engine version=0.18.0 used for min-check is lower than model.min_engine_version=0.19.0"
    assert any(msg in r.message for r in caplog.records)


def test_device_count_written_to_resolution_notes_without_polluting_engine_config(monkeypatch):
    model_data = _make_model_data(min_engine_version=None, schema_version=None)
    platform_data: Dict[str, Any] = {}
    _patch_loader_outputs(monkeypatch, model_data=model_data, platform_data=platform_data)

    resolved_with_device_count = resolve_config(
        ResolvedEnv(
            config_root=Path("/tmp/config"),
            hardware=HardwareContext("h100", "nvidia", {}),
            engine_version=_make_engine_version(requested="0.19.0"),
        ),
        Target(model_name="unit-test-model", topology=Topology.STANDALONE, engine="vllm"),
        device_count=8,
    )
    notes_with_device_count = resolved_with_device_count.resolution_notes
    assert notes_with_device_count["device_count"] == "8"
    assert notes_with_device_count["device_count_source"] == "provided"
    assert "device_count" not in resolved_with_device_count.engine_config_traces

    resolved_without_device_count = resolve_config(
        ResolvedEnv(
            config_root=Path("/tmp/config"),
            hardware=HardwareContext("h100", "nvidia", {}),
            engine_version=_make_engine_version(requested="0.19.0"),
        ),
        Target(model_name="unit-test-model", topology=Topology.STANDALONE, engine="vllm"),
    )
    notes_without_device_count = resolved_without_device_count.resolution_notes
    assert notes_without_device_count["device_count"] == "unset"
    assert notes_without_device_count["device_count_source"] == "unset"
    assert "device_count" not in resolved_without_device_count.engine_config_traces
