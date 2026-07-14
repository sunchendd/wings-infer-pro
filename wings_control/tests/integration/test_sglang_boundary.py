"""sglang 引擎支持集成测试(docs/49 落地)。

历史:本文件曾是"边界表征"测试(sglang 渲染层未支持,build_argv 报 Unknown engine)。
docs/49 落地后 sglang 已支持,遂转为**正向渲染断言**:
- ✅ 配置解析 + 合并(引擎无关主流水线)对 sglang 正常;
- ✅ 渲染产出 `python3 -m sglang.launch_server --model-path <model> ...`(启动入口 + model 具名,
  非 vllm 位置式);recipe 键(如 tp)按 sglang 原生名渲染。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wings_ctl.core.config_resolver import resolve_config
from wings_ctl.core.models import ResolvedEnv, Target
from wings_ctl.core.topology import Topology
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SGLANG_RECIPE = _REPO_ROOT / "config" / "engines" / "sglang" / "v0.5.14" / "h200" / "models" / "DeepSeek-V3"

_skip = pytest.mark.skipif(
    not _SGLANG_RECIPE.exists(),
    reason="缺 sglang recipe(config/engines/sglang/v0.5.14/h200/models/DeepSeek-V3)",
)


def _resolve_sglang(config_root_real: Path, tmp_path: Path, monkeypatch):
    """跑到 resolve_config(不渲染),返回 sglang 的 ResolvedConfig。"""
    monkeypatch.setenv("ENGINE_VERSION", "0.5.14")
    for k in ("RANK_IP", "NODE_IPS", "MASTER_IP", "PD_ROLE",
              "ENABLE_SPECULATIVE_DECODE", "ENABLE_KV_OFFLOAD"):
        monkeypatch.delenv(k, raising=False)
    hw_file = tmp_path / "hw.json"
    hw_file.write_text(json.dumps({"hardware_family": "h200", "device": "nvidia", "count": 8}))
    hardware = resolve_hardware(hw_file)
    engine_version = resolve_engine_version(config_root_real, hardware.hardware_family, engine="sglang")
    return resolve_config(
        ResolvedEnv(config_root=config_root_real, hardware=hardware, engine_version=engine_version),
        Target(model_name="DeepSeek-V3", topology=Topology.STANDALONE, engine="sglang"),
    )


@_skip
def test_sglang_config_resolves_engine_agnostic(config_root_real, tmp_path, monkeypatch):
    """✅ 主流水线引擎无关:sglang recipe 能被解析+合并,traces 含 model/tp(不 if-engine)。"""
    resolved = _resolve_sglang(config_root_real, tmp_path, monkeypatch)
    assert resolved.engine == "sglang"
    assert resolved.engine_config_traces["model"].final_value == "deepseek-ai/DeepSeek-V3"
    assert resolved.engine_config_traces["tp"].final_value == 8


@_skip
def test_sglang_render_produces_launch_server(config_root_real, tmp_path, monkeypatch):
    """✅ 渲染:sglang 产出 `python3 -m sglang.launch_server --model-path <model> ...`(model 具名,非位置)。"""
    resolved = _resolve_sglang(config_root_real, tmp_path, monkeypatch)
    argv = build_argv(resolved.engine_config_traces, engine="sglang")
    # 启动入口(命令规格 docs/49 §3.1)
    assert argv[:3] == ["python3", "-m", "sglang.launch_server"]
    # model 具名 --model-path <value>(非位置;非 vllm 的 serve 形态)
    assert argv[3] == "--model-path" and argv[4] == "deepseek-ai/DeepSeek-V3"
    assert "serve" not in argv
    # recipe 键按 sglang 原生名渲染(tp → --tp 8)
    assert "--tp" in argv and "8" in argv
