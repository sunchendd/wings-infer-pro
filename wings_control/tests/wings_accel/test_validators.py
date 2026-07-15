from wings_accel.schemas import (
    SmartAccelInput,
    SystemConfig,
    ModelConfig,
    EngineConfig,
    SmartDecodingConfig,
    SmartKVCacheConfig,
    SmartKVSparseConfig,
    DeploymentMode,
)
from wings_accel.validators import collect_smart_accel_warnings


def make_input(**overrides):
    defaults = dict(
        hardware_config=SystemConfig(),
        model_config=ModelConfig(model_path="/models/llama"),
        engine_config=EngineConfig(),
        deployment_mode=DeploymentMode(),
        smart_decoding_config=SmartDecodingConfig(),
        smart_kv_cache_config=SmartKVCacheConfig(),
        smart_kv_sparse_config=SmartKVSparseConfig(),
    )
    defaults.update(overrides)
    return SmartAccelInput(**defaults)


def test_collect_warnings_all_disabled_empty():
    assert not collect_smart_accel_warnings(make_input())


def test_validate_kv_missing_disk_path():
    kv = SmartKVCacheConfig(enabled=True, disk_offload_enabled=True, disk_capacity_gb=100, disk_path="")
    warnings = collect_smart_accel_warnings(make_input(smart_kv_cache_config=kv))
    assert any("disk_path" in w.lower() for w in warnings)


def test_validate_kv_disk_without_memory():
    kv = SmartKVCacheConfig(
        enabled=True, memory_offload_enabled=False,
        disk_offload_enabled=True, disk_capacity_gb=100, disk_path="/mnt/kv",
    )
    warnings = collect_smart_accel_warnings(make_input(smart_kv_cache_config=kv))
    assert any("memory" in w.lower() for w in warnings)


def test_validate_decoding_missing_arch():
    dec = SmartDecodingConfig(enabled=True, model_path="/draft/eagle")
    mod = ModelConfig(model_path="/models/llama", model_arch=None)
    warnings = collect_smart_accel_warnings(make_input(smart_decoding_config=dec, model_config=mod))
    assert any("model_arch" in w.lower() for w in warnings)
