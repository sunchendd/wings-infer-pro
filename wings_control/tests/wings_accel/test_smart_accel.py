"""wings-accel 接入适配器单测(docs/40)。

覆盖:collect_output 扁平汇总(四个 EngineParams,含 None 子产出)、模块缺失 no-op、
stub 模块端到端、build_smart_input 兼容旧调用映射。
"""

from __future__ import annotations

import types

from wings_ctl.accel import smart_accel
from wings_ctl.accel.smart_accel import (
    AccelResult,
    apply_smart_accel,
    build_smart_input,
    collect_accel_switches,
    collect_output,
)


# ── stub:模拟 wings-accel resolver 模块 ───────────────────────────────────

class _Out:
    """模拟 EngineParams(engine_config/env)。"""

    def __init__(self, engine_config=None, env=None):
        self.engine_config = engine_config or {}
        self.env = env or {}


class _SmartOutput:
    """模拟 SmartAccelOutput(scheme + 合并后的 EngineParams)。"""

    def __init__(self, engine_params=None, decoding_scheme=None, kv_scheme=None, sparse_scheme=None, diagnostics=None):
        self.engine_params = engine_params or _Out()
        self.smart_decoding_scheme = decoding_scheme
        self.smart_kv_cache_scheme = kv_scheme
        self.smart_kv_sparse_scheme = sparse_scheme
        self.diagnostics = diagnostics or {}


def _make_stub_module():
    """构造一个 duck-typed 假 wings-accel 模块:dataclass 用 kwargs 存成 SimpleNamespace。"""
    mod = types.SimpleNamespace()
    for name in (
        "SystemConfig", "ModelConfig", "EngineConfig", "DeploymentMode",
        "SmartDecodingConfig", "SmartKVCacheConfig", "SmartKVSparseConfig", "SmartAccelInput",
    ):
        setattr(mod, name, lambda **kw: types.SimpleNamespace(**kw))

    def _resolve_smart_accel_from_config(**kwargs):
        flags = kwargs.get("flags")
        if flags and flags.decoding_enabled:
            return _SmartOutput(
                engine_params=_Out(engine_config={"speculative_config": {"method": "suffix"}}),
                decoding_scheme="suffix",
            )
        return _SmartOutput()

    mod.LoadFlags = lambda **kw: types.SimpleNamespace(**kw)
    mod.resolve_smart_accel_from_config = _resolve_smart_accel_from_config
    return mod


# ── collect_output ─────────────────────────────────────────────────────────

def test_collect_flattens_outputs() -> None:
    """验证 EngineParams 的 cli/env 被汇总,scheme 进 audit。"""
    out = _SmartOutput(
        engine_params=_Out(
            engine_config={"speculative_config": {}, "kv_transfer_config": {}, "mamba_cache": True},
            env={"LMCACHE_X": "1"},
        ),
        decoding_scheme="mtp",
        kv_scheme="cpu",
    )
    result = collect_output(out)
    assert result.engine_config == {"speculative_config": {}, "kv_transfer_config": {}, "mamba_cache": True}
    assert result.env == {"LMCACHE_X": "1"}
    assert result.audit == {"smart_decoding_scheme": "mtp", "smart_kv_cache_scheme": "cpu"}  # 裸内容;emitter 包 wings_accel
    assert result.enabled is True


def test_collect_handles_empty_output() -> None:
    """验证空输出时不报错、不产出 audit。"""
    result = collect_output(_SmartOutput())
    assert result.engine_config == {}
    assert result.audit == {}


def test_collect_output_writes_diagnostics_to_wings_accel_audit() -> None:
    """验证 SmartAccelOutput.diagnostics 原样落入 wings_accel audit 段。"""
    out = _SmartOutput(
        decoding_scheme="suffix",
        diagnostics={"decoding": {"degraded": True, "degrade_reason": "mtp_conflict->suffix"}},
    )
    result = collect_output(out)
    assert result.audit == {
        "smart_decoding_scheme": "suffix",
        "diagnostics": {"decoding": {"degraded": True, "degrade_reason": "mtp_conflict->suffix"}},
    }


# ── apply_smart_accel ──────────────────────────────────────────────────────

def test_apply_module_absent_is_noop(monkeypatch) -> None:
    """验证 wings-accel 模块不在场 → 返回空 AccelResult(no-op)。"""
    monkeypatch.setattr(smart_accel, "_import_accel", lambda: None)
    result = apply_smart_accel(
        hardware_family="h100", gpu_count=8, model_path="/m", model_name="M",
        engine="vllm", engine_version="0.19.0", env={"ENABLE_SPECULATIVE_DECODE": "true"},
    )
    assert result == AccelResult()
    assert result.enabled is False


def test_apply_with_stub_module_appends_spec(monkeypatch) -> None:
    """验证 stub 模块在场 + spec 开 → cli 含 --speculative-config、诊断进 audit。"""
    monkeypatch.setattr(smart_accel, "_import_accel", _make_stub_module)
    result = apply_smart_accel(
        hardware_family="h100", gpu_count=8, model_path="/m", model_name="M",
        engine="vllm", engine_version="0.19.0", env={"ENABLE_SPECULATIVE_DECODE": "true"},
    )
    assert result.enabled is True
    assert result.engine_config["speculative_config"]["method"] == "suffix"
    assert result.audit == {"smart_decoding_scheme": "suffix"}  # 裸内容;emitter 包 wings_accel


def test_apply_with_stub_module_spec_off_no_config(monkeypatch) -> None:
    """未显式 ENABLE_SPECULATIVE_DECODE 时 decoding_enabled=False。"""
    monkeypatch.setattr(smart_accel, "_import_accel", _make_stub_module)
    result = apply_smart_accel(
        hardware_family="h100", gpu_count=8, model_path="/m", model_name="M",
        engine="vllm", engine_version="0.19.0", env={},
    )
    assert result.engine_config == {}
    assert result.enabled is False  # 产空 = 未启用(不触发 install 段);对齐 enabled="成功产出"语义


# ── build_smart_input(仅兼容旧单测/旧调用)──────────────────────────────────

def test_build_input_maps_env_switches() -> None:
    """验证 spec/kv/sparse 三类配置从 env 正确映射,model_arch 不传,smart_accel 为空。"""
    mod = _make_stub_module()
    env = {
        "ENABLE_SPECULATIVE_DECODE": "true",
        "SPECULATIVE_DECODE_MODEL_PATH": "/draft",
        "ENABLE_KV_OFFLOAD": "true",
        "ENABLE_KV_MEM_OFFLOAD": "true",
        "KV_MEM_OFFLOAD_SIZE": "128",
        "ENABLE_SPARSE": "true",
        "SPARSE_LEVEL": "accuracy_first",
        "AVAILABLE_POD_MEM_SIZE": "512",
    }
    si = build_smart_input(
        mod, hardware_family="h200", gpu_count=4, model_path="/m", model_name="M",
        engine="vllm", engine_version="0.19.0", switches=collect_accel_switches(env),
    )
    assert si.hardware_config.gpu_type == "h200"
    assert si.hardware_config.pod_available_memory_gb == 512
    assert si.smart_decoding_config.enabled is True
    assert si.smart_decoding_config.model_path == "/draft"
    assert si.smart_kv_cache_config.enabled is True
    assert si.smart_kv_cache_config.memory_offload_enabled is True
    assert si.smart_kv_cache_config.memory_offload_size_mode == "128"
    assert si.smart_kv_sparse_config.enabled is True
    assert si.smart_kv_sparse_config.mode == "accuracy_first"
    assert si.smart_accel == {}  # 仅兼容旧单测/旧调用,不代表生产路径
    assert not hasattr(si.model_config, "model_arch") or si.model_config.model_arch is None


def test_build_input_maps_auto_kv_mem_offload_size() -> None:
    mod = _make_stub_module()
    si = build_smart_input(
        mod, hardware_family="h200", gpu_count=4, model_path="/m", model_name="M",
        engine="vllm", engine_version="0.19.0",
        switches=collect_accel_switches({"ENABLE_KV_MEM_OFFLOAD": "true", "KV_MEM_OFFLOAD_SIZE": "auto"}),
    )
    assert si.smart_kv_cache_config.enabled is True
    assert si.smart_kv_cache_config.memory_offload_enabled is True
    assert si.smart_kv_cache_config.memory_offload_size_mode == "auto"
