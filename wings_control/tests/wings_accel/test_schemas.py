from wings_accel.schemas import (
    SmartAccelInput,
    SmartAccelOutput,
    GeneratedFile,
    EngineParams,
    SystemConfig,
    ModelConfig,
    EngineConfig,
    SmartDecodingConfig,
    SmartKVCacheConfig,
    SmartKVSparseConfig,
    DeploymentMode,
)


def test_smart_accel_output_defaults():
    """验证 SmartAccelOutput 默认无 scheme、无参数、无降级诊断。"""
    out = SmartAccelOutput()
    assert out.smart_decoding_scheme is None
    assert out.smart_kv_cache_scheme is None
    assert out.smart_kv_sparse_scheme is None
    assert out.engine_params.env == {}
    assert out.engine_params.engine_config == {}
    assert out.diagnostics == {}
    assert out.pre_serve_trusted is None


def test_smart_accel_output_diagnostics_default_isolated():
    """验证 diagnostics 使用独立默认 dict,避免实例间污染。"""
    first = SmartAccelOutput()
    second = SmartAccelOutput()
    first.diagnostics["decoding"] = {"degraded": True}
    assert second.diagnostics == {}


def test_smart_accel_output_generated_files_default_isolated():
    """验证 generated_files 使用独立默认 list,避免实例间污染。"""
    first = SmartAccelOutput()
    second = SmartAccelOutput()

    first.generated_files.append(
        GeneratedFile(path="/shared-volume/a", content="a")
    )

    assert second.generated_files == []


def test_engine_params_defaults():
    ep = EngineParams()
    assert ep.env == {}
    assert ep.engine_config == {}


def test_smart_accel_input_creation():
    inp = SmartAccelInput(
        hardware_config=SystemConfig(gpu_type="H100", gpu_count=8, pod_available_memory_gb=256),
        model_config=ModelConfig(model_path="/models/llama", model_name="Llama-3-70B", model_arch="llama"),
        engine_config=EngineConfig(name="vllm", version="0.11.0"),
        deployment_mode=DeploymentMode(pd_role=None),
        smart_decoding_config=SmartDecodingConfig(enabled=False),
        smart_kv_cache_config=SmartKVCacheConfig(enabled=False),
        smart_kv_sparse_config=SmartKVSparseConfig(enabled=False),
    )
    assert inp.hardware_config.gpu_type == "H100"
    assert inp.hardware_config.pod_available_memory_gb == 256
    assert inp.model_config.model_name == "Llama-3-70B"
    assert inp.model_config.model_arch == "llama"
    assert inp.smart_accel == {}  # 默认空 smart_accel 块


def test_system_config_defaults():
    sysc = SystemConfig()
    assert sysc.gpu_type == "A100"
    assert sysc.gpu_count == 1
    assert sysc.pod_available_memory_gb == 0


def test_kv_cache_config_defaults():
    kv = SmartKVCacheConfig()
    assert kv.enabled is False
    assert kv.memory_offload_enabled is False
    assert kv.memory_offload_size_mode == ""
    assert kv.disk_offload_enabled is False
    assert kv.disk_capacity_gb == 0
    assert kv.disk_path == ""
    assert kv.qat_enabled is False
