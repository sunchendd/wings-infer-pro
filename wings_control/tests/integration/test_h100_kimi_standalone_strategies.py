from __future__ import annotations

import json
import os
import subprocess

import pytest

from wings_ctl.core.models import PipelineRequest, Target
from wings_ctl.core.topology import Topology
from wings_ctl.pipeline import run_pipeline


pytestmark = pytest.mark.skip(
    reason="h100 Kimi无standalone场景,待Step3.1 topology;非2a回归"
)


def test_h100_kimi_standalone_strategies_pipeline_and_source_path(config_root_real, tmp_path):
    """h100 Kimi-K2.5 使用 strategies 嵌套格式时可跑通,trace 指向 strategies 路径。"""
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "h100", "device": "nvidia", "count": 8}),
        encoding="utf-8",
    )

    os.environ["ENGINE_VERSION"] = "0.19.0"
    try:
        out_dir = tmp_path / "kimi_h100_standalone"
        resolved, start_path, repro_path, audit_path = run_pipeline(
            PipelineRequest(
                target=Target(model_name="Kimi-K2.5", topology=Topology.STANDALONE, engine="vllm"),
                hardware_info_path=hardware_info_path,
                config_root=config_root_real,
            ),
            output_dir=out_dir,
        )

        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        model_trace = audit["engine_config"]["model"]
        assert model_trace["final_layer"] == "model_scenario"
        assert model_trace["source_path"].startswith("scenarios.standalone.strategies.")
        assert model_trace["source_path"].endswith(".engine_config.model")
        assert "Kimi-K2.5-int4.yaml" in model_trace["source_file"]

        from wings_ctl.engines.vllm_adapter import build_argv

        argv = build_argv(resolved.engine_config_traces, engine="vllm")
        assert argv[0:2] == ["vllm", "serve"]
        assert "moonshotai/Kimi-K2.5" in argv

        # echo 方式执行生成脚本(不真实拉起服务)
        content = start_path.read_text(encoding="utf-8")
        patched = content.replace("exec ", "echo ", 1)
        env = os.environ.copy()
        env.setdefault("LD_PRELOAD", "")
        proc = subprocess.run(["bash"], input=patched, capture_output=True, text=True, env=env)
        assert proc.returncode == 0
        assert "vllm serve" in proc.stdout
    finally:
        os.environ.pop("ENGINE_VERSION", None)
