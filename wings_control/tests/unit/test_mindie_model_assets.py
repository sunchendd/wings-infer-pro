from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from wings_ctl.loaders.locator import load_model_config


@pytest.mark.parametrize("hardware_family", ["ascend-a2", "ascend-a3"])
def test_deepseek_moe_profile_matches_and_carries_ep_policy(
    hardware_family: str,
) -> None:
    """A2/A3 使用同一用户无感 EP 契约，模型差异完全来自静态 YAML。"""
    repo_root = Path(__file__).resolve().parents[2]
    data, path, matched = load_model_config(
        repo_root / "config",
        hardware_family,
        "mindie",
        "2.3.0",
        "DeepSeek-R1-W8A8",
        has_version_dir=True,
    )

    assert path is not None
    assert path.name == "deepseek_moe.yaml"
    assert matched
    assert data is not None
    for scenario_name in ("standalone", "multi_node"):
        scenario = data["scenarios"][scenario_name]
        config = scenario["engine_config"]
        assert config["mindie_is_moe"] is True
        assert config["mindie_ep_enabled"] is True
        assert config["mindie_moe_tp"] == 1
        assert config["mindie_ep_level"] == 1
        assert scenario["env"]["ATB_LLM_COMM_BACKEND"] == "hccl"


@pytest.mark.parametrize("hardware_family", ["ascend-a2", "ascend-a3"])
def test_deepseek_distill_does_not_match_moe_profile(hardware_family: str) -> None:
    """Distill 名称不能触发 MoE/EP profile，避免稠密权重按专家并行启动。"""
    repo_root = Path(__file__).resolve().parents[2]
    data, path, matched = load_model_config(
        repo_root / "config",
        hardware_family,
        "mindie",
        "2.3.0",
        "DeepSeek-R1-Distill-Qwen-32B",
        has_version_dir=True,
    )

    assert (data, path, matched) == (None, None, "")


def test_mindie_complete_template_and_platform_env_assets_are_valid() -> None:
    """完整 JSON 与两套平台 YAML 是运行时唯一静态资产，必须可独立解析。"""
    repo_root = Path(__file__).resolve().parents[2]
    version_dir = repo_root / "config" / "engines" / "mindie" / "v2.3.0"
    template = json.loads((version_dir / "mindie_service_config.json").read_text(encoding="utf-8"))
    assert template["Version"] == "1.0.0"
    assert template["ServerConfig"]["managementPort"] == 1026
    assert template["BackendConfig"]["ModelDeployConfig"]["ModelConfig"]
    assert template["BackendConfig"]["ScheduleConfig"]["maxBatchSize"] == 200

    for hardware_family in ("ascend-a2", "ascend-a3"):
        platform = yaml.safe_load(
            (version_dir / hardware_family / "models" / "default_model.yaml").read_text(encoding="utf-8")
        )
        env = platform["platform_env"]
        assert env["MINDIE_LOG_TO_STDOUT"] == "1"
        assert env["PYTORCH_NPU_ALLOC_CONF"] == "expandable_segments:True"
        assert env["HCCL_CONNECT_TIMEOUT"] == "7200"
