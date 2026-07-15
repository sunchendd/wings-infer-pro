from wings_accel import func_smart_accel
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


def make_input(
    dec_enabled=False, sparse_enabled=False, offload_enabled=False,
    model_arch="", draft_model_path="", kv_cache_config=None,
    smart_accel=None, engine="vllm", **overrides
):
    defaults = dict(
        hardware_config=SystemConfig(gpu_type="H100", gpu_count=8, pod_available_memory_gb=256),
        model_config=ModelConfig(model_path="/models/llama", model_arch=model_arch),
        engine_config=EngineConfig(name=engine, version="0.23.0"),
        deployment_mode=DeploymentMode(pd_role=None),
        smart_decoding_config=SmartDecodingConfig(enabled=dec_enabled, model_path=draft_model_path),
        smart_kv_cache_config=kv_cache_config or SmartKVCacheConfig(enabled=offload_enabled),
        smart_kv_sparse_config=SmartKVSparseConfig(enabled=sparse_enabled),
        smart_accel=smart_accel if smart_accel is not None else make_smart_accel(),
    )
    defaults.update(overrides)
    return SmartAccelInput(**defaults)


def make_smart_accel():
    """smart_accel 模板块(new:list 形式)。每次构造全新 dict,避免测试间污染。"""
    return {
        "decoding": [
            {"name": "eagle3", "requires_model_path": True, "priority": 2,
             "cli_params": {"speculative_config": {"method": "eagle3", "num_speculative_tokens": 3}}},
            {"name": "mtp", "priority": 1,
             "cli_params": {"speculative_config": {"method": "mtp", "num_speculative_tokens": 1}}},
        ],
        "sparse": [
            {"name": "performance_first", "priority": 2,
             "cli_params": {"hf_overrides": {"use_index_cache": True, "index_topk_freq": 4}}},
            {"name": "accuracy_first", "priority": 1,
             "cli_params": {"hf_overrides": {"use_index_cache": True, "index_topk_freq": 8}}},
        ],
        "kv_offload": [
            {"name": "cpu",
             "cli_params": {"kv_transfer_config": {
                 "kv_connector": "OffloadingConnector", "kv_role": "kv_both",
                 "kv_connector_extra_config": {"num_cpu_blocks": "{mem_gb_to_blocks}"}}}},
            {"name": "disk",
             "cli_params": {"kv_transfer_config": {"kv_connector": "LMCacheConnectorV1", "kv_role": "kv_both"}}},
        ],
    }


def test_all_disabled():
    """验证全部特性关闭时无 scheme、无参数、无 diagnostics。"""
    out = func_smart_accel(make_input())
    assert out.smart_decoding_scheme is None
    assert out.smart_kv_sparse_scheme is None
    assert out.smart_kv_cache_scheme is None
    assert out.engine_params.engine_config == {}
    assert out.engine_params.env == {}
    assert out.diagnostics == {}


def test_decoding_only_hit():
    """验证 decoding 正常命中时只写 scheme,不写降级 diagnostics。"""
    inp = make_input(dec_enabled=True, model_arch="eagle3", draft_model_path="/draft/eagle")
    out = func_smart_accel(inp)
    assert out.smart_decoding_scheme is not None
    assert out.smart_decoding_scheme == "eagle3"
    assert out.smart_kv_sparse_scheme is None
    assert out.smart_kv_cache_scheme is None
    assert out.diagnostics == {}


def test_all_three_with_mtp_kv_no_conflict():
    """mtp + kvoffload 可同时生效。"""
    kv_cfg = SmartKVCacheConfig(
        enabled=True, memory_offload_enabled=True, memory_offload_size_mode="64",
        disk_offload_enabled=True, disk_capacity_gb=200, disk_path="/mnt/kv",
    )
    inp = make_input(dec_enabled=True, sparse_enabled=True, kv_cache_config=kv_cfg)
    # 强制 model_based 不命中 → 落到 mtp
    inp.smart_accel["decoding"] = [inp.smart_accel["decoding"][1]]
    out = func_smart_accel(inp)
    assert out.smart_decoding_scheme == "mtp"
    assert out.smart_kv_sparse_scheme is not None
    assert out.smart_kv_cache_scheme is not None


def test_all_three_no_conflict():
    kv_cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=True, memory_offload_size_mode="64")
    inp = make_input(
        dec_enabled=True, model_arch="eagle3", draft_model_path="/draft/eagle",
        sparse_enabled=True, kv_cache_config=kv_cfg,
    )
    out = func_smart_accel(inp)
    assert out.smart_decoding_scheme == "eagle3"
    assert out.smart_kv_sparse_scheme is not None
    assert out.smart_kv_cache_scheme is not None


def test_empty_smart_accel():
    """smart_accel 为空 → decoding 输出 None。"""
    out = func_smart_accel(make_input(dec_enabled=True, smart_accel={}))
    assert out.smart_decoding_scheme is None


def test_decoding_degrade_writes_diagnostics():
    """验证 decoding 降级时 diagnostics 只记录 decoding 降级原因。"""
    block = {**make_smart_accel()}
    block["decoding"] = [
        {"name": "mtp", "priority": 1, "cli_params": {"speculative_config": {"method": "mtp"}}},
    ]
    out = func_smart_accel(make_input(
        dec_enabled=True, draft_model_path="/draft/unknown", smart_accel=block,
    ))
    assert out.smart_decoding_scheme == "mtp"
    assert out.diagnostics == {
        "decoding": {"degraded": True, "degrade_reason": "model_based_miss->no_model"},
    }


def test_sparse_degrade_writes_diagnostics():
    """验证 sparse 降级时 diagnostics 只记录 sparse 降级原因。"""
    block = {**make_smart_accel()}
    block["sparse"] = [
        {"name": "accuracy_first", "cli_params": {"hf_overrides": {"use_index_cache": True}}},
    ]
    out = func_smart_accel(make_input(sparse_enabled=True, smart_accel=block))
    assert out.smart_kv_sparse_scheme == "accuracy_first"
    assert out.diagnostics == {
        "sparse": {"degraded": True, "degrade_reason": "performance_first_miss->accuracy_first"},
    }


def test_pd_prefill_disables_decoding():
    kv_cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=True, memory_offload_size_mode="64")
    inp = make_input(
        dec_enabled=True, model_arch="eagle3", draft_model_path="/draft/eagle",
        sparse_enabled=True, kv_cache_config=kv_cfg,
        deployment_mode=DeploymentMode(pd_role="prefill"),
    )
    out = func_smart_accel(inp)
    assert out.smart_decoding_scheme is None  # prefill 短路
    assert out.smart_kv_sparse_scheme is not None
    assert out.smart_kv_cache_scheme is not None


def test_sglang_all_none():
    """sglang 引擎 → 全部 None。"""
    out = func_smart_accel(make_input(dec_enabled=True, engine="sglang"))
    assert out.smart_decoding_scheme is None
    assert out.smart_kv_sparse_scheme is None
    assert out.smart_kv_cache_scheme is None
    assert out.engine_params.engine_config == {}
    assert out.diagnostics == {}


def test_custom_features_only_when_smart_on():
    """custom_features 仅在 decoding/kv/sparse 至少一项产出时才启用。"""
    custom = {"custom_features": [
        {"name": "Mamba prefix caching", "cli_params": {"mamba_cache": True}},
    ]}
    # 全关 → custom 不启用
    out = func_smart_accel(make_input(smart_accel={**make_smart_accel(), **custom}))
    assert out.engine_params.engine_config == {}
    # 开 decoding → custom 启用
    out2 = func_smart_accel(make_input(
        dec_enabled=True, model_arch="eagle3", draft_model_path="/draft/eagle",
        smart_accel={**make_smart_accel(), **custom},
    ))
    assert out2.engine_params.engine_config["mamba_cache"] is True
