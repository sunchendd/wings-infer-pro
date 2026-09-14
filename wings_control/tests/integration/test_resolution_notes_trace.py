from __future__ import annotations

import json
import logging
import os

from wings_ctl.core.config_resolver import _load_model_config
from wings_ctl.core.topology import Topology
from wings_ctl.core.models import PipelineRequest, ResolvedEnv, Target
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.pipeline import run_pipeline


def test_resolution_notes_normal(config_root_real, tmp_path):
    """正常场景:resolution_notes 含全部 6 个查找轨迹 key,值均为 str,内容正确。"""
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )

    os.environ["ENGINE_VERSION"] = "v0.18.0"
    try:
        out_dir = tmp_path / "normal"
        _, _, _, audit_path = run_pipeline(
            PipelineRequest(
                target=Target(model_name="kimi-k2.5", topology=Topology.STANDALONE, engine="vllm-ascend"),
                hardware_info_path=hardware_info_path,
                config_root=config_root_real,
            ),
            output_dir=out_dir,
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        notes = audit.get("resolution_notes", {})

        assert "resolved_version_dir" in notes
        assert "version_is_fallback" in notes
        assert "requested_version" in notes
        assert "resolved_version" in notes
        assert "matched_model_yaml" in notes
        assert "matched_name_pattern" in notes

        for k, v in notes.items():
            if k == "fallback":
                assert isinstance(v, bool), f"{k} is {type(v).__name__}, expected bool"
            else:
                assert isinstance(v, str), f"{k} is {type(v).__name__}, expected str"

        assert notes["matched_model_yaml"].endswith("Kimi-K2.5.yaml")
        assert notes["matched_name_pattern"] != ""
        assert notes["version_is_fallback"] == "false"
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def test_resolution_notes_fallback(config_root_real, tmp_path):
    """ENGINE_VERSION=99.99.99:version_is_fallback=true,requested=99.99.99,resolved 指向 latest。"""
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )

    os.environ["ENGINE_VERSION"] = "99.99.99"
    try:
        out_dir = tmp_path / "fallback"
        _, _, _, audit_path = run_pipeline(
            PipelineRequest(
                target=Target(model_name="kimi-k2.5", topology=Topology.STANDALONE, engine="vllm-ascend"),
                hardware_info_path=hardware_info_path,
                config_root=config_root_real,
            ),
            output_dir=out_dir,
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        notes = audit.get("resolution_notes", {})

        assert notes["version_is_fallback"] == "true"
        assert notes["requested_version"] == "99.99.99"
        latest_version = resolve_engine_version(
            config_root_real, "ascend-a3", engine="vllm-ascend"
        ).resolved
        assert notes["resolved_version"] == latest_version
        assert notes["resolved_version_dir"].endswith(latest_version)
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def test_load_model_config_returns_pattern(config_root_real):
    """load_model_config 返回 3 元组,第三个元素是命中的 name_pattern。"""
    data, yaml_path, pattern = _load_model_config(
        config_root=config_root_real,
        hardware_family="ascend-a3",
        engine="vllm-ascend",
        version="v0.18.0",
        model_name="DeepSeek-V4-Flash",
    )
    assert isinstance(pattern, str)
    assert len(pattern) > 0
    assert "DeepSeek-V4-Flash" in yaml_path.name


def test_no_match_fallback_success_with_warn_and_flag(config_root_real, tmp_path, caplog):
    """no-match 解析阶段走 default_model 兜底,并记录 fallback/warning/layer 语义。"""
    from wings_ctl.core.config_resolver import resolve_config
    from wings_ctl.engines.version_resolver import resolve_engine_version
    from wings_ctl.hardware.resolver import resolve_hardware

    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )

    os.environ["ENGINE_VERSION"] = "v0.18.0"
    try:
        hardware = resolve_hardware(hardware_info_path)
        engine_version = resolve_engine_version(
            config_root_real, hardware.hardware_family, engine="vllm-ascend"
        )
        with caplog.at_level(logging.WARNING):
            resolved = resolve_config(
                ResolvedEnv(config_root=config_root_real, hardware=hardware, engine_version=engine_version),
                Target(model_name="NonExistentModel-999B", topology=Topology.STANDALONE, engine="vllm-ascend"),
            )

        notes = resolved.resolution_notes
        assert notes["fallback"] is True
        assert any(
            "No model recipe matched; falling back to platform defaults" in rec.message for rec in caplog.records
        )

        layers = {entry.final_layer for entry in resolved.engine_config_traces.values()}
        # 兜底分支不使用 model_scenario；请求模型名由独立 request_default 层补齐。
        assert "model_scenario" not in layers
        assert layers.issubset(
            {"builtin_default", "default_model", "request_default", "strategy_device_count", "user_cli"}
        )
        model_trace = resolved.engine_config_traces["model"]
        assert model_trace.final_layer == "request_default"
        assert model_trace.source_file == "<request>"
        assert model_trace.source_path == "request.model"
    finally:
        os.environ.pop("ENGINE_VERSION", None)
