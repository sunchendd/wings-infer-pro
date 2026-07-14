"""E2E tests for real tool-generated YAML format (Step 2.1 adaptation).

NOTE: nvidia-RTX5880 platform deleted by wings-config overwrite (2026-06).
Tests that verified no-platform-default behavior (test_a–test_e) removed accordingly.
Surviving tests: test_f (extra blocks), test_g (ambiguous), test_h (no-match).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from wings_ctl.core.config_resolver import resolve_config, _load_model_config
from wings_ctl.core.models import ResolvedEnv, Target
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.hardware.resolver import resolve_hardware


def _resolve_ascend(config_root_real: Path):
    """Helper: resolve DeepSeek-V4-Flash on ascend-a3."""
    hw_path = Path("/tmp/ascend_hw.json")
    if not hw_path.exists():
        hw_path.write_text(
            json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
            encoding="utf-8",
        )
    os.environ["ENGINE_VERSION"] = "0.18.0"
    try:
        hardware = resolve_hardware(hw_path)
        engine_version = resolve_engine_version(
            config_root_real, hardware.hardware_family, engine="vllm-ascend"
        )
        resolved = resolve_config(
            ResolvedEnv(config_root=config_root_real, hardware=hardware, engine_version=engine_version),
            Target(model_name="DeepSeek-V4-Flash", topology=Topology.STANDALONE, engine="vllm-ascend"),
        )
        return resolved
    finally:
        os.environ.pop("ENGINE_VERSION", None)


class TestRealFormatE2E:
    """真实工具产物格式端到端测试。"""

    def test_f_no_extra_blocks_cause_error(
        self, config_root_real
    ):
        """(f) yaml 内 hardware_profile / features / tuning_overrides 等块不报错。"""
        resolved = _resolve_ascend(config_root_real)
        assert resolved is not None
        # 确认 extra blocks 不影响核心解析(命中 model 时不叠 default_model)
        assert "model" in resolved.engine_config_traces

    def test_g_ambiguous_match_raises_value_error(
        self, config_root_real, tmp_path
    ):
        """(g) 同一 models_dir 下两个 yaml 都匹配 model_name 时 raise ValueError。"""
        models_dir = (
            tmp_path / "engines" / "vllm-ascend" / "v0.18.0" / "ascend-a3" / "models"
        )
        model_subdir = models_dir / "DeepSeek-V4-Flash"
        model_subdir.mkdir(parents=True)

        yaml_content = """
model:
  name: DeepSeek-V4-Flash
  match:
    - name_pattern: "(?i)deepseek[-.]?v4[-.]?flash"
scenarios:
  standalone:
    engine_config:
      model: deepseek-ai/DeepSeek-V4-Flash
    env: {}
"""
        (model_subdir / "DeepSeek-V4-Flash-fp8.yaml").write_text(yaml_content)
        (model_subdir / "DeepSeek-V4-Flash-bf16.yaml").write_text(yaml_content)

        with pytest.raises(ValueError, match="Ambiguous"):
            _load_model_config(
                config_root=tmp_path,
                hardware_family="ascend-a3",
                engine="vllm-ascend",
                version="0.18.0",
                model_name="DeepSeek-V4-Flash",
            )

    def test_h_no_match_returns_none_tuple(self, config_root_real):
        """(h) 无匹配 model_name 时返回 (None, None, "")。"""
        data, path, pattern = _load_model_config(
            config_root=config_root_real,
            hardware_family="ascend-a3",
            engine="vllm-ascend",
            version="0.18.0",
            model_name="NonExistentModel-999B",
        )
        assert data is None
        assert path is None
        assert pattern == ""
