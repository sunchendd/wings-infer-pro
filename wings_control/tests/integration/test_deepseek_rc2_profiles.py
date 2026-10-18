"""Validate the two rc2 single-node profiles without importing an inference engine."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from wings_accel import func_smart_accel
from wings_accel.yaml_loader import LoadFlags, load_smart_accel_from_yaml
from wings_ctl.loaders.reasoning_table import load_reasoning_table
from wings_ctl.loaders.v2_loader import locate_v2
from wings_ctl.strategy.reasoning_resolver import ModelIdentity, resolve_reasoning

CONFIG = Path(__file__).resolve().parents[2] / "config"


@dataclass(frozen=True)
class ProfileCase:
    model: str
    speculative_tokens: int
    memcache_port: int
    memcache_protocol: str


CASES = [
    ProfileCase("DeepSeek-V4-Flash-0731-w8a8", 7, 19500, "host_shm"),
    ProfileCase("DeepSeek-V4-Flash-Vision-Exp-w8a8-QuaRot", 6, 15000, "device_sdma"),
]


def asset_for(model, cpu="aarch64", hardware="Ascend910C_64G", version="v0.30.0rc2"):
    return locate_v2(CONFIG, {"engine": "vllm-ascend", "version": version,
                             "hardware": hardware, "model": model, "cpu_arch": cpu})


def expand(asset, *, kv=False, decoding=False, sparse=False, level="accuracy_first", capacity="128", available=0):
    flags = LoadFlags(kv=kv, decoding_enabled=decoding, sparse=sparse,
                      sparse_level=level, topology="standalone",
                      memory_offload_size_mode=capacity, pod_available_memory_gb=available,
                      tp_size=4, dp_size=4, gpu_count=16)
    return func_smart_accel(load_smart_accel_from_yaml(asset.path, flags))


@pytest.mark.parametrize("case", CASES)
def test_profile_cpu_hardware_and_version_boundaries(case):
    asset = asset_for(case.model)
    assert asset is not None and asset.model["variant_name"] == case.model
    assert set(asset.scenarios) == {"standalone"}
    assert asset_for(case.model, cpu="x86_64") is None
    assert asset_for(case.model, hardware="Ascend910B_64G") is None
    assert asset_for(case.model, version="v0.30.0rc1") is None


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("level", ["accuracy_first", "performance_first"])
def test_all_three_features_and_memcache_capacity(case, level):
    asset = asset_for(case.model)
    baseline = asset.scenarios["standalone"]["strategies"]["single_node"]["engine_config"]
    assert baseline["max_model_len"] == 1048576
    assert baseline["tensor_parallel_size"] == baseline["data_parallel_size"] == 4
    assert baseline["port"] == 17000 and baseline["block_size"] == 32
    output = expand(asset, kv=True, decoding=True, sparse=True, level=level)
    config = output.engine_params.engine_config
    assert config["speculative_config"] == {
        "method": "dspark", "num_speculative_tokens": case.speculative_tokens, "enforce_eager": True,
    }
    expected_sparse_config = {"use_index_cache": True, "index_topk_freq": 8 if level == "performance_first" else 4}
    assert config["hf_overrides"] == expected_sparse_config
    assert config["kv_transfer_config"]["kv_connector"] == "AscendStoreConnector"
    assert config["kv_transfer_config"]["kv_connector_extra_config"]["backend"] == "memcache"
    assert output.packages == []
    contents = "\n".join(item.content for item in output.generated_files)
    assert "8GB" in contents and "world_size = 256" in contents
    assert f"protocol = {case.memcache_protocol}" in contents and str(case.memcache_port) in contents
    assert any("start_kv_serve.sh" in command for command in output.pre_serve_master)
    source_commands = asset.scenarios["standalone"]["strategies"]["single_node"]["system_setup"]["commands"]
    assert any(command.startswith("source ") and "prepare.sh" in command for command in source_commands)
    assert any(item.path.endswith("prepare.sh") for item in output.generated_files)


@pytest.mark.parametrize("case", CASES)
def test_engine_patches_are_not_selected_as_model_packages(case):
    asset = asset_for(case.model)
    output = expand(asset)
    assert output.packages == []
    assert output.engine_params.engine_config == {}
    assert not output.generated_files
    assert not output.pre_serve_master
    assert expand(asset, kv=True).packages == []


@pytest.mark.parametrize("case", CASES)
def test_memcache_downgrade_does_not_select_compatibility_packages(case):
    output = expand(asset_for(case.model), kv=True, capacity="auto", available=1)
    assert "kv_transfer_config" not in output.engine_params.engine_config
    assert output.packages == []


@pytest.mark.parametrize("case", CASES)
def test_function_call_and_reasoning_compatibility(case):
    asset = asset_for(case.model)
    tool_args = asset.features["tool_calling"]["args"]
    assert "--enable-auto-tool-choice" in tool_args
    assert tool_args[tool_args.index("--tool-call-parser") + 1] == "deepseek_v4"
    assert asset.features["reasoning"]["args"] == ["--reasoning-parser", "deepseek_v4"]
    table = load_reasoning_table(CONFIG)
    resolution = resolve_reasoning(table.data, ModelIdentity(case.model, case.model), "vllm-ascend")
    assert resolution.status == "matched"
    assert resolution.spec.args == ("--reasoning-parser", "deepseek_v4")
