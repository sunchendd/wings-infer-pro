"""全开 / 全关 demo:三模型真实 SmartAccel 输出。

用真有 smart-accel 资产的三模型(vllm / rtx_pro_5000_48G / v0.23.0):
- DeepSeek-V4-Flash(decoding + sparse;kv_offload 已移除:v0.22.0 不支持)
- MiniMax-M2.7(decoding=suffix;无 kv_offload/sparse)
- Qwen3.5-397B-A17B(decoding + kv_offload)

跑"全开" LoadFlags 看真实 scheme + engine_config + env(`pytest -s` 可见打印);
并验证"全关(裸 LoadFlags())"三模型全空 no-op(守 LoadFlags 默认全 False,MaaS 选择即开启)。
"""

import pytest

from wings_accel.api import resolve_smart_accel_from_config
from wings_accel.yaml_loader import LoadFlags

# 三模型均自带 smart-accel 资产(vllm / v0.23.0 / rtx_pro_5000_48G)
MODELS = ["DeepSeek-V4-Flash", "MiniMax-M2.7", "Qwen3.5-397B-A17B"]

# 全开:decoding + kv 内存卸载 + sparse(disk/qat 因生产 yaml 无 disk scheme 不触发)
ALL_ON = LoadFlags(
    decoding_enabled=True,
    kv=True,
    memory_offload_size_mode="64",
    sparse=True,
)


def _resolve(model: str, flags: LoadFlags):
    """以包内 smart-accel 资产解析单模型,返回 SmartAccelOutput。

    DeepSeek-V4-Flash 资产在 v0.22.0(该引擎版本不支持 kv 卸载,yaml 已移至 v0.22.0);
    其余模型在 v0.23.0。
    """
    version = "0.22.0" if model == "DeepSeek-V4-Flash" else "0.23.0"
    return resolve_smart_accel_from_config(
        engine="vllm",
        engine_version=version,
        hardware_family="rtx_pro_5000_48G",
        model_name=model,
        flags=flags,
        config_root="",
    )


@pytest.mark.parametrize("model", MODELS)
def test_all_on_real_output(model):
    """全开:三模型真实输出(各按 yaml 支持的特性产出)。pytest -s 看打印。"""
    out = _resolve(model, ALL_ON)
    assert out is not None
    ec = out.engine_params.engine_config
    env = out.engine_params.env
    print(f"\n══ {model} (all-on) ══")
    print(
        f"  schemes : dec={out.smart_decoding_scheme!r} "
        f"kv_cache={out.smart_kv_cache_scheme!r} sparse={out.smart_kv_sparse_scheme!r}"
    )
    print(f"  engine_config: {ec}")
    print(f"  env          : {env}")

    if model == "DeepSeek-V4-Flash":
        # decoding + sparse(kv_offload 已移除:v0.22.0 不支持)
        assert out.smart_decoding_scheme == "mtp"
        assert out.smart_kv_cache_scheme is None
        assert out.smart_kv_sparse_scheme == "performance_first"
        assert "speculative_config" in ec and "kv_transfer_config" not in ec
        assert ec["hf_overrides"]["index_topk_freq"] == 8
        # kv_cache_dtype 由 engine_config baseline 提供,smart-accel sparse 块不再重复声明
        assert "kv_cache_dtype" not in ec
    elif model == "MiniMax-M2.7":
        # decoding=suffix + kv_offload=cpu(资产新增独立 cpu scheme:仅开内存时走 lmcache cpu-only)
        assert out.smart_decoding_scheme == "suffix"
        assert out.smart_kv_cache_scheme == "cpu"
        assert out.smart_kv_sparse_scheme is None
        assert "speculative_config" in ec and "kv_transfer_config" in ec
        assert ec["speculative_config"]["method"] == "suffix"
        assert env["LMCACHE_LOCAL_CPU"] == "True"  # 内存侧保留
        assert not any("DISK" in k for k in env)  # cpu-only:env 无 DISK 相关键
        assert out.packages == []  # 资产未声明 packages(lmcache 镜像预装)
    else:  # Qwen3.5-397B-A17B
        # decoding + kv_offload(cpu)(yaml 无 sparse 块)
        assert out.smart_decoding_scheme == "mtp"
        assert out.smart_kv_cache_scheme == "cpu"
        assert out.smart_kv_sparse_scheme is None


@pytest.mark.parametrize("model", MODELS)
def test_all_off_is_noop(model):
    """全关(裸 LoadFlags()):三模型全空 no-op(守 LoadFlags 默认全 False)。"""
    out = _resolve(model, LoadFlags())
    assert out is not None
    assert out.smart_decoding_scheme is None
    assert out.smart_kv_cache_scheme is None
    assert out.smart_kv_sparse_scheme is None
    assert out.engine_params.engine_config == {}
    assert out.engine_params.env == {}
