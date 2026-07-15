from wings_accel.render import PlaceholderContext
from wings_accel.schemas import SmartKVSparseConfig
from wings_accel.sparse import smart_sparse_expander


def make_block():
    """new:list 形式,每个 scheme 的 name 为 mode 门键。"""
    return [
        {
            "name": "performance_first",
            "cli_params": {"hf_overrides": {"use_index_cache": True, "index_topk_freq": 4}},
            "envs": {},
        },
        {
            "name": "accuracy_first",
            "cli_params": {"hf_overrides": {"use_index_cache": True, "index_topk_freq": 8}},
            "envs": {},
        },
    ]


def test_sparse_disabled():
    cfg = SmartKVSparseConfig(enabled=False)
    assert smart_sparse_expander(cfg, None, PlaceholderContext()) is None


def test_sparse_performance_hit():
    cfg = SmartKVSparseConfig(enabled=True, mode="performance_first")
    out = smart_sparse_expander(cfg, make_block(), PlaceholderContext())
    assert out.scheme == "performance_first"
    assert out.degraded is False
    assert out.engine_params.engine_config["hf_overrides"]["index_topk_freq"] == 4


def test_sparse_accuracy_hit():
    cfg = SmartKVSparseConfig(enabled=True, mode="accuracy_first")
    out = smart_sparse_expander(cfg, make_block(), PlaceholderContext())
    assert out.scheme == "accuracy_first"
    assert out.degraded is False
    assert out.engine_params.engine_config["hf_overrides"]["index_topk_freq"] == 8


def test_sparse_performance_miss_degrade_to_accuracy():
    block = [
        {
            "name": "accuracy_first",
            "cli_params": {"hf_overrides": {"use_index_cache": True, "index_topk_freq": 8}},
        },
    ]
    cfg = SmartKVSparseConfig(enabled=True, mode="performance_first")
    out = smart_sparse_expander(cfg, block, PlaceholderContext())
    assert out.scheme == "accuracy_first"
    assert out.degraded is True
    assert "performance_first_miss->accuracy_first" in out.degrade_reason


def test_sparse_empty_fallback():
    cfg = SmartKVSparseConfig(enabled=True, mode="performance_first")
    assert smart_sparse_expander(cfg, [], PlaceholderContext()) is None


def test_sparse_missing_mode_returns_none():
    block = [{"name": "other", "cli_params": {"kv_cache_dtype": "fp8"}}]
    cfg = SmartKVSparseConfig(enabled=True, mode="performance_first")
    assert smart_sparse_expander(cfg, block, PlaceholderContext()) is None
