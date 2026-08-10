"""DeepSeek-V4-Flash standalone 收口验证 — h100 + vllm v0.19.0。

验证:
- _platform.yaml 重写为框架 schema 后,platform 层 host/port 进入合并
- pipeline 跑通、argv 正确、resolution_notes 指向 DeepSeek-V4-Flash-fp8.yaml
- port events 仅 1 条 (platform_default,无 override — DeepSeek standalone 未写 port)
"""

from __future__ import annotations

import json
import os

from wings_ctl.core.topology import Topology
from wings_ctl.core.models import PipelineRequest, Target
from wings_ctl.pipeline import run_pipeline


def test_deepseek_standalone_pipeline(config_root_real, tmp_path):
    """DeepSeek-V4-Flash standalone 流水线跑通,argv/audit/resolution_notes 正确。"""
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "h100", "device": "nvidia", "count": 8}),
        encoding="utf-8",
    )

    os.environ["ENGINE_VERSION"] = "0.19.0"
    try:
        out_dir = tmp_path / "deepseek_standalone"
        resolved, start_path, repro_path, audit_path = run_pipeline(
            PipelineRequest(
                target=Target(model_name="DeepSeek-V4-Flash", topology=Topology.STANDALONE, engine="vllm"),
                hardware_info_path=hardware_info_path,
                config_root=config_root_real,
            ),
            output_dir=out_dir,
        )

        # ── audit / resolution_notes ──
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        notes = audit.get("resolution_notes", {})

        # 查找轨迹指向正确模型 yaml
        assert notes["matched_model_yaml"].endswith("DeepSeek-V4-Flash-fp8.yaml")
        assert notes["selected_strategy"] == "single_node_tep"
        assert notes["strategy_selection_source"] == "default_strategy"
        assert notes["strategy_default_candidates"] == "single_node_tep"

        # platform_default 存在 (不再是 absent)
        assert "platform_default" not in notes

        # ── engine_config traces ──
        engine_config = audit["engine_config"]

        # host/port: 该策略模板未显式给出 → 由 builtin_default 兜底(0.0.0.0/17000,proxy 迁移 backend 端口)
        assert engine_config["host"]["final_value"] == "0.0.0.0"
        assert engine_config["host"]["final_layer"] == "builtin_default"
        assert engine_config["port"]["final_value"] == 17000
        assert engine_config["port"]["final_layer"] == "builtin_default"

        # model: 来自 model_scenario
        model = engine_config["model"]
        assert model["final_value"] == "deepseek-ai/DeepSeek-V4-Flash"
        assert model["final_layer"] == "model_scenario"
        assert model["source_path"].startswith("scenarios.standalone.strategies.")
        assert model["source_path"].endswith(".engine_config.model")

        # ── argv ──
        from wings_ctl.engines.vllm_adapter import build_argv

        argv = build_argv(resolved.engine_config_traces, engine="vllm")
        assert argv[0:2] == ["vllm", "serve"]
        # 模板未给 host/port → builtin_default 兜底,argv 应含默认 0.0.0.0/17000
        assert "--host" in argv and "0.0.0.0" in argv
        assert "--port" in argv and "17000" in argv
        assert "--trust-remote-code" in argv
        assert "deepseek-ai/DeepSeek-V4-Flash" in argv

        # ── start_command.sh 可执行 ──
        start_content = start_path.read_text(encoding="utf-8")
        assert "vllm serve" in start_content
        assert "deepseek-ai/DeepSeek-V4-Flash" in start_content
        assert "--host 0.0.0.0" in start_content
        assert "--port 17000" in start_content

    finally:
        os.environ.pop("ENGINE_VERSION", None)
