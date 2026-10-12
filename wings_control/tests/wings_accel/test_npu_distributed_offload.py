"""vLLM-Ascend Mooncake NPU runtime regression tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from wings_accel.distributed_offload import (
    apply_mooncake_script_fallback,
    resolve_mooncake_runtime,
    smart_distributed_kv_offload_expander,
)
from wings_accel.render import PlaceholderContext
from wings_accel.schemas import DistributedKVCacheConfig, SmartAccelConfigurationError


def _ctx() -> PlaceholderContext:
    return PlaceholderContext(memory_capacity_gb=32, memory_offload_enabled=True)


def _cfg() -> DistributedKVCacheConfig:
    return DistributedKVCacheConfig(
        enabled=True,
        protocol="ascend",
        serving_config_id="npu-order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
    )


def _npu_block(*, delivery=None):
    scheme = {
        "name": "mooncake_standalone_store",
        "runtime": "mooncake_npu",
        "client": {
            "rpc_port": 50052,
            "master_rpc_port": 50051,
            "metadata_port": 10080,
            "metadata_path": "/metadata",
        },
        # The production connector is pinned only after the Ascend compatibility
        # spike; resolver safety is independent of its engine-specific value.
        "cli_params": {
            "kv_transfer_config": {
                "kv_connector": "ValidatedAscendStandaloneConnector",
                "kv_role": "kv_both",
            }
        },
    }
    if delivery is not None:
        scheme["delivery"] = delivery
    return [scheme]


def _accel_volume(tmp_path: Path, monkeypatch, package: str, version: str = "v0.3.12.post1") -> None:
    root = tmp_path / "accel-volume"
    (root / "packages" / package / version).mkdir(parents=True)
    monkeypatch.setenv("ACCEL_VOLUME_PATH", str(root))


def test_runtime_selection_is_engine_based() -> None:
    assert resolve_mooncake_runtime("vllm").runtime_id == "mooncake_cuda"
    assert resolve_mooncake_runtime("vllm_ascend").package_name == "xcache_npu"
    with pytest.raises(SmartAccelConfigurationError, match="supports only vllm"):
        resolve_mooncake_runtime("sglang")


def test_npu_fallback_selects_xcache_npu_and_npu_assets(tmp_path, monkeypatch) -> None:
    _accel_volume(tmp_path, monkeypatch, "xcache_npu")

    output = smart_distributed_kv_offload_expander(
        _cfg(),
        _npu_block(delivery={"mode": "fallback"}),
        _ctx(),
        engine_name="vllm-ascend",
        topology="multi_node",
    )
    output = apply_mooncake_script_fallback(_cfg(), output, engine_name="vllm-ascend", topology="multi_node")

    assert output is not None
    assert output.mooncake_runtime == "mooncake_npu"
    assert output.mooncake_transfer_engine_package == "xcache_npu:v0.3.12.post1"
    assert [item.manifest for item in output.packages] == ["xcache_npu:v0.3.12.post1"]
    assert output.mooncake_script_assets_required is True
    assert output.mooncake_component_sources["runtime"] == "mooncake_npu"
    assert output.mooncake_component_sources["transfer_engine"] == "injected"
    assert 'bash "$SHARED_VOLUME_PATH/distributed_offload/mooncake_npu/start_mooncake_store.sh" &' in output.pre_serve
    assert "start_mooncake_master.sh" in "\n".join(output.mooncake_master_section)


@pytest.mark.parametrize(
    ("engine", "runtime"),
    [("vllm", "mooncake_npu"), ("vllm-ascend", "mooncake_cuda")],
)
def test_runtime_must_match_engine(engine: str, runtime: str) -> None:
    block = _npu_block()
    block[0]["runtime"] = runtime
    with pytest.raises(SmartAccelConfigurationError, match="incompatible"):
        smart_distributed_kv_offload_expander(_cfg(), block, _ctx(), engine_name=engine)


def test_npu_rejects_pd_topology() -> None:
    with pytest.raises(SmartAccelConfigurationError, match="supports only"):
        smart_distributed_kv_offload_expander(
            _cfg(), _npu_block(), _ctx(), engine_name="vllm-ascend", topology="pd_decode"
        )


def test_npu_assets_are_separate_and_require_recipe_hccl_identity() -> None:
    from wings_ctl.rendering.script_builder import _resolve_mooncake_assets_dir

    # 调用 resolver 确保 runtime 名受支持；源码断言避免受测试容器镜像资产影响。
    _resolve_mooncake_assets_dir("mooncake_npu")
    # 当前源码必须从独立的 mooncake_npu 目录读取 NPU asset。
    source_assets = Path(__file__).resolve().parents[2] / "src" / "wings_accel" / "distributed_offload" / "mooncake_npu"
    assert source_assets.is_dir()
    store_script = (source_assets / "start_mooncake_store.sh").read_text(encoding="utf-8")
    json_script = (source_assets / "creat_mooncake_json.sh").read_text(encoding="utf-8")
    master_script = (source_assets / "start_mooncake_master.sh").read_text(encoding="utf-8")
    assert "function set_ascend_env()" in store_script
    assert 'source ${CUR_PATH}/client.env' in store_script
    assert "KV_PROTOCOL" in store_script
    assert 'source "${CUR_PATH}/client.env"' in json_script
    assert 'source "${CUR_PATH}/master.env"' in master_script


def test_fallback_uses_runtime_specific_distributed_offload_directory(tmp_path, monkeypatch) -> None:
    """NPU fallback command paths must resolve under its isolated runtime directory."""
    _accel_volume(tmp_path, monkeypatch, "xcache_npu")
    output = smart_distributed_kv_offload_expander(
        _cfg(), _npu_block(delivery={"mode": "fallback"}), _ctx(), engine_name="vllm-ascend"
    )
    output = apply_mooncake_script_fallback(_cfg(), output, engine_name="vllm-ascend")

    assert output is not None
    rendered = "\n".join(output.pre_serve)
    assert "$SHARED_VOLUME_PATH/distributed_offload/mooncake_npu/client.env" not in rendered
    assert "$SHARED_VOLUME_PATH/distributed_offload/mooncake_npu/creat_mooncake_json.sh" in rendered
    assert "$SHARED_VOLUME_PATH/distributed_offload/mooncake_npu/start_mooncake_store.sh" in rendered
    assert "MOONCAKE_CONFIG_PATH" not in rendered
    assert "$SHARED_VOLUME_PATH/distributed_offload/mooncake_cuda" not in rendered


def test_npu_fallback_json_makes_vllm_a_pure_store_requester(tmp_path) -> None:
    """NPU vLLM must not create an in-process SSD owner in standalone mode."""
    import subprocess

    source_assets = Path(__file__).resolve().parents[2] / "src" / "wings_accel" / "distributed_offload" / "mooncake_npu"
    script = tmp_path / "creat_mooncake_json.sh"
    script.write_text((source_assets / "creat_mooncake_json.sh").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "client.env").write_text(
        "\n".join(
            [
                "export SERVING_CONFIG_ID=npu-order-7",
                "export KV_PROTOCOL=ascend",
                "export KV_MEM_OFFLOAD_SIZE=32",
                "export ENABLE_KV_MEM_OFFLOAD=true",
                "export ENABLE_KV_DISK_OFFLOAD=true",
                "export KV_DISK_OFFLOAD_PATH=/mnt/mooncake",
                "export KV_DISK_OFFLOAD_SIZE=128",
                "",
            ]
        ),
        encoding="utf-8",
    )
    subprocess.run(
        ["bash", str(script)],
        check=True,
        env={**os.environ, "SHARED_VOLUME_PATH": str(tmp_path)},
        capture_output=True,
        text=True,
    )

    import json

    config = json.loads((tmp_path / "distributed_offload" / "mooncake_npu" / "mooncake.json").read_text())
    assert config == {
        "mode": "standalone-store",
        "metadata_server": "P2PHANDSHAKE",
        "master_server_address": "mooncake-service-npu-order-7:50051",
        "global_segment_size": 0,
        "protocol": "ascend",
        "device_name": "",
        "preferred_segment": False,
        "prefer_alloc_in_same_node": True,
        "enable_ssd_offload": False,
    }
    assert "ssd_offload_path" not in config


def test_full_yaml_requires_all_runtime_components_inside_mooncake_volume(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    _accel_volume(tmp_path, monkeypatch, "xcache_npu")
    delivery = {
        "mode": "full_yaml",
        "envs": {"KV_PROTOCOL": "ascend", "HCCL_IF_IP": "10.0.0.1"},
    }
    block = _npu_block(delivery=delivery)
    block[0]["files"] = [
        {"path": "distributed_offload/mooncake_npu/mooncake.json", "content": "{}"},
        {
            "path": "distributed_offload/mooncake_npu/start_mooncake_store.sh",
            "scope": "all",
            "mode": "0755",
            "content": "#!/usr/bin/env bash\n",
        },
        {
            "path": "distributed_offload/mooncake_npu/start_mooncake_master.sh",
            "scope": "master",
            "mode": "0755",
            "content": "#!/usr/bin/env bash\n",
        },
    ]

    output = smart_distributed_kv_offload_expander(
        _cfg(), block, _ctx(), engine_name="vllm-ascend", topology="standalone"
    )
    output = apply_mooncake_script_fallback(_cfg(), output, engine_name="vllm-ascend", topology="standalone")

    assert output is not None
    assert output.mooncake_script_assets_required is False
    assert output.mooncake_env_files_required is True
    assert output.mooncake_env_overrides == {"KV_PROTOCOL": "ascend", "HCCL_IF_IP": "10.0.0.1"}
    assert output.mooncake_config_path == str(tmp_path / "distributed_offload" / "mooncake_npu" / "mooncake.json")
    assert output.mooncake_component_sources["env"] == "yaml"
    assert output.mooncake_component_sources["start_mooncake_store.sh"] == "yaml"
    assert output.mooncake_component_sources["start_mooncake_master.sh"] == "yaml"


def test_full_yaml_rejects_file_outside_mooncake_volume(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    block = _npu_block(delivery={"mode": "full_yaml", "envs": {"KV_PROTOCOL": "ascend"}})
    block[0]["files"] = [
        {"path": "outside.json", "content": "{}"},
        {"path": "distributed_offload/mooncake_npu/start_mooncake_store.sh", "scope": "all", "content": "#!/bin/sh\n"},
        {
            "path": "distributed_offload/mooncake_npu/start_mooncake_master.sh",
            "scope": "master",
            "content": "#!/bin/sh\n",
        },
    ]
    with pytest.raises(SmartAccelConfigurationError, match="must stay under"):
        smart_distributed_kv_offload_expander(_cfg(), block, _ctx(), engine_name="vllm-ascend", topology="standalone")
