"""导游测试(维护者向)—— 最小 standalone 链路走读。

这个测试是**给维护者看的导游测试**,不是为了增加覆盖或堆复杂 fixture:
用一个最简单的 standalone 例子,把 wings-control 主链路串成一条可读的故事——
CLI / pipeline 输入 → ResolvedConfig / trace → start_command.sh / repro.sh / audit.json。
读完这个测试,新人应能对"参数从哪来、到哪去、audit 怎么解释"建立整体印象。

复用现有 `config_root_real` 真实配置资产(h100 + DeepSeek-V4-Flash + vllm),不新造 config。
"""

from __future__ import annotations

import json

from wings_ctl.core.topology import Topology
from wings_ctl.core.models import PipelineRequest, Target, UserInput
from wings_ctl.pipeline import run_pipeline
from wings_ctl.translators.cli_translator import CLITranslator


def test_standalone_pipeline_walkthrough_shows_cli_to_artifacts(
    config_root_real, tmp_path, monkeypatch
):
    """导游:最小 standalone 链路,从 CLI 输入一路走到三件产物 + audit trace。"""
    # 1. Prepare minimal inputs
    #    硬件信息 + 模型名 + 引擎/版本 —— 这就是 MaaS/CLI 下发给 wings-control 的最小输入。
    monkeypatch.setenv("ENGINE_VERSION", "0.19.0")
    hardware_info_path = tmp_path / "hardware_info.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "h100", "device": "nvidia"}),
        encoding="utf-8",
    )
    #    一个用户具名参数(--max-num-seqs 128):真实 CLI 里由 CLITranslator 把它翻成 canonical key,
    #    这里直接调 translator 展示这一步,再把结果交给 pipeline(user_cli 是最高优先级覆盖层)。
    user_cli, user_cli_dropped = CLITranslator.translate_overrides({"max_num_seqs": 128}, "vllm")

    # 2. Run pipeline
    #    run_pipeline = 解析(hardware → version → config 深合并)+ 渲染脚本 + 出 audit,一次调用。
    out_dir = tmp_path / "walkthrough_out"
    resolved, start_path, repro_path, audit_path = run_pipeline(
        PipelineRequest(
            target=Target(model_name="DeepSeek-V4-Flash", topology=Topology.STANDALONE, engine="vllm"),
            hardware_info_path=hardware_info_path,
            config_root=config_root_real,
            user_input=UserInput(cli_overrides=user_cli, cli_dropped=user_cli_dropped),
        ),
        output_dir=out_dir,
    )

    # 3. Check resolved config
    #    ResolvedConfig 是核心产物:standalone 无多机 nodes;engine_config_traces 是"逐参数 (值, trace)"。
    assert resolved.topology == Topology.STANDALONE
    assert resolved.engine == "vllm"
    assert resolved.nodes is None                       # standalone 恒无 per-node 视图
    assert resolved.engine_config_traces                # 非空:至少有 model / host / port 等

    # 4. Check rendered scripts
    #    两件脚本产物:start_command.sh(可执行)+ repro.sh(每个参数带来源注释,便于复现/排查)。
    assert start_path.exists() and repro_path.exists()
    start_content = start_path.read_text(encoding="utf-8")
    assert "vllm serve" in start_content           # 命令头:vllm serve <model>
    repro_content = repro_path.read_text(encoding="utf-8")
    assert "Reproducibility Script" in repro_content     # repro 头
    assert "<-" in repro_content                         # 每个参数标了"来自哪层(哪文件)"

    # 5. Check audit trace
    #    audit.json 回答"每个参数最终值 / 来源层 / 覆盖历史"。挑 model 看一条完整 trace。
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    model_trace = audit["engine_config"]["model"]
    assert model_trace["final_value"] == "deepseek-ai/DeepSeek-V4-Flash"
    assert model_trace["final_layer"] == "model_scenario"    # 值来自模型 recipe 层
    assert model_trace["events"]                             # events = 完整来源链(set / override)
    assert model_trace["events"][0]["action"] and model_trace["events"][0]["layer"]

    #    用户传入的 --max-num-seqs 能在 audit 里被解释:既进 user_cli_params(applied),
    #    也让该参数的 final_layer 落到 user_cli(user_cli 是最高优先级覆盖层)。
    applied_keys = {p.get("key") for p in audit.get("user_cli_params", []) if p.get("status") == "applied"}
    assert "max_num_seqs" in applied_keys
    assert audit["engine_config"]["max_num_seqs"]["final_layer"] == "user_cli"
