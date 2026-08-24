from __future__ import annotations

import json
import os

from wings_ctl.core.topology import Topology
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.core.models import PipelineRequest, Target, UserInput
from wings_ctl.pipeline import run_pipeline
from wings_ctl.translators.cli_translator import CLITranslator


def test_named_params_translate_to_argv_and_audit(config_root_real, tmp_path):
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )

    raw_overrides = {
        "model_name": "Qwen3-30B-A3B",
        "model_path": "/tmp/models/",
        "port": 18000,
        "max_num_seqs": 256,
        "trust_remote_code": True,
        "input_length": 4096,
        "output_length": 4096,
        "gpu_memory_utilization": 0.9,
        "seed": 42,
        "quantization": "fp8",
        "enable_prefix_caching": True,
        "enable_expert_parallel": True,
    }
    translated, dropped = CLITranslator.translate_overrides(raw_overrides, "vllm-ascend")

    os.environ["ENGINE_VERSION"] = "v0.18.0"
    try:
        out_dir = tmp_path / "named_params"
        resolved, _, _, audit_path = run_pipeline(
            PipelineRequest(
                target=Target(model_name="Qwen3-Next", topology=Topology.STANDALONE, engine="vllm-ascend"),
                hardware_info_path=hardware_info_path,
                config_root=config_root_real,
                user_input=UserInput(cli_overrides=translated, cli_dropped=dropped),
            ),
            output_dir=out_dir,
        )
    finally:
        os.environ.pop("ENGINE_VERSION", None)

    argv = build_argv(resolved.engine_config_traces, engine="vllm-ascend")
    argv_text = " ".join(argv)
    assert argv[0:2] == ["vllm", "serve"]
    assert "/tmp/models/" in argv
    assert "--served-model-name" in argv_text and "Qwen3-30B-A3B" in argv_text
    assert "--port 18000" in argv_text
    assert "--max-num-seqs 256" in argv_text
    assert "--trust-remote-code" in argv
    assert "--input-length" not in argv_text
    assert "--output-length" not in argv_text
    # 评审定:gpu_memory_utilization / seed 直通(user_cli 覆盖 recipe)→ 进 argv
    assert "--gpu-memory-utilization 0.9" in argv_text
    assert "--seed 42" in argv_text
    # 不在 MaaS contract allowlist:warn+dropped,不进最终 argv
    assert "--quantization" not in argv_text
    assert "--enable-prefix-caching" not in argv_text
    assert "--enable-expert-parallel" not in argv_text

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["engine_config"]["served_model_name"]["final_value"] == "Qwen3-30B-A3B"
    assert audit["engine_config"]["served_model_name"]["final_layer"] == "user_cli"
    assert audit["engine_config"]["seed"]["final_layer"] == "user_cli"
    dropped_rows = [
        r
        for r in audit.get("user_cli_params", [])
        if r.get("status") == "dropped"
    ]
    dropped_keys = {row.get("key") for row in dropped_rows}
    assert {
        "input_length",
        "output_length",
        "quantization",
        "enable_prefix_caching",
        "enable_expert_parallel",
    }.issubset(dropped_keys)
    assert "seed" not in dropped_keys and "gpu_memory_utilization" not in dropped_keys
    dropped_reason_by_key = {row.get("key"): row.get("reason") for row in dropped_rows}
    assert dropped_reason_by_key.get("quantization") == "maas_status=not_in_maas_contract_allowlist"
    assert dropped_reason_by_key.get("enable_prefix_caching") == "maas_status=not_in_maas_contract_allowlist"
    assert dropped_reason_by_key.get("enable_expert_parallel") == "maas_status=not_in_maas_contract_allowlist"
    assert all("reason" in row for row in dropped_rows)
