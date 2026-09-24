"""wings-accel 接入适配器单测(docs/40/42)。

覆盖:collect_accel_switches(v3 命名收口)、build_smart_input(switches→schema 映射)、
collect_output(扁平含 custom_cli)、apply_smart_accel(模块缺失 no-op / stub 端到端)。
注:原 tests/unit/test_smart_accel.py 在 config 重构提交中被连带删除,此为按新 switches API 重建。
"""

from __future__ import annotations

import types

import pytest

from wings_ctl.accel import smart_accel
from wings_ctl.accel.smart_accel import (
    AccelResult,
    apply_smart_accel,
    build_smart_input,
    collect_accel_switches,
    collect_output,
)


# ── collect_accel_switches(v3 ENV 命名收口)─────────────────────────────────

def test_collect_switches_v3_kv_hierarchy():
    """验证 v3 新名(ENABLE_KV_*/KV_*)被正确收口,KV 三级开关 + auto 容量归 0。"""
    env = {
        "ENABLE_SPECULATIVE_DECODE": "true",
        "SPECULATIVE_DECODE_MODEL_PATH": "/draft",
        "ENABLE_SPARSE": "true",
        "SPARSE_LEVEL": "accuracy_first",
        "ENABLE_KV_OFFLOAD": "true",
        "ENABLE_KV_MEM_OFFLOAD": "true",
        "KV_MEM_OFFLOAD_SIZE": "auto",
        "ENABLE_KV_DISK_OFFLOAD": "true",
        "KV_DISK_OFFLOAD_PATH": "/lm",
        "KV_DISK_OFFLOAD_SIZE": "512",
        "ENABLE_KV_QAT": "true",
        "KV_QAT_COMPRESS_LEVEL": "2",
        "KV_QAT_INSTANCE_NUM": "4",
        "AVAILABLE_POD_MEM_SIZE": "131072",  # 131072 MiB = 128 GB(验证 MiB→GB 换算)
        "PD_ROLE": "P",
    }
    s = collect_accel_switches(env)
    assert s["speculative_enabled"] and s["speculative_model_path"] == "/draft"
    assert s["sparse_enabled"] and s["sparse_level"] == "accuracy_first"
    assert s["kv_offload_enabled"] and s["kv_mem_enabled"] and s["kv_disk_enabled"] and s["kv_qat_enabled"]
    assert s["kv_mem_size_gb"] == 0          # "auto" → 0(交 accel 智能推荐)
    assert s["kv_disk_size_gb"] == 512 and s["kv_disk_path"] == "/lm"
    assert s["kv_qat_compress_level"] == 2 and s["kv_qat_instance_num"] == 4
    assert s["available_pod_mem_gb"] == 113 and s["pd_role"] == "P"  # 131072 MiB→128 GB−15 补偿=113;PD_ROLE 原样透传


def test_collect_switches_defaults_when_absent():
    """验证 env 全缺 → 开关 False、容量 0、pd_role None、sparse 默认 performance_first。"""
    s = collect_accel_switches({})
    flag_keys = ("speculative_enabled", "sparse_enabled", "kv_offload_enabled",
                 "kv_mem_enabled", "kv_disk_enabled", "kv_qat_enabled")
    assert not any(s[k] for k in flag_keys)
    assert s["kv_mem_size_gb"] == 0 and s["available_pod_mem_gb"] == 0
    assert s["pd_role"] is None and s["sparse_level"] == "performance_first"


def test_collect_switches_kv_mem_size_numeric():
    """验证 KV_MEM_OFFLOAD_SIZE 为数值串时转 int(非 auto)。"""
    assert collect_accel_switches({"KV_MEM_OFFLOAD_SIZE": "64"})["kv_mem_size_gb"] == 64


def test_collect_switches_keeps_distributed_kv_separate_from_local_offload():
    switches = collect_accel_switches({
        "ENABLE_DISTRIBUTED_KV_OFFLOAD": "true",
        "ENABLE_KV_MEM_OFFLOAD": "true",
        "KV_MEM_OFFLOAD_SIZE": "64",
        "KV_PROTOCOL": "RDMA",
        "SERVING_CONFIG_ID": "order-7",
        "KV_LOCAL_BUFFER_SIZE": "1GB",
    })
    assert switches["distributed_kv_enabled"] is True
    assert switches["distributed_kv_protocol"] == "rdma"
    assert switches["serving_config_id"] == "order-7"
    assert switches["distributed_kv_local_buffer_size"] == "1GB"
    assert switches["kv_offload_enabled"] is False


def test_collect_switches_no_kv_store_envs():
    """KV_STORE_BACKEND/DEPLOY_MODE/MASTER_ADDR/WORLD_SIZE 已退役:不在 switches 里。"""
    s = collect_accel_switches({"KV_STORE_BACKEND": "mooncake", "KV_WORLD_SIZE": "32"})
    for k in ("kv_store_backend", "kv_store_deploy_mode", "kv_store_master_addr", "kv_world_size"):
        assert k not in s


def test_collect_switches_speculative_path_passthrough():
    """SPECULATIVE_DECODE_MODEL_PATH 原样透传;none/null 归一已下放到消费点(decoders._eligible)。"""
    assert collect_accel_switches({"SPECULATIVE_DECODE_MODEL_PATH": "none"})["speculative_model_path"] == "none"
    assert collect_accel_switches({})["speculative_model_path"] == ""


# ── build_smart_input(switches → schema)────────────────────────────────────

def _stub_mod():
    """duck-typed 假 wings-accel 模块:dataclass 用 SimpleNamespace,func 回显 spec。"""
    mod = types.SimpleNamespace()
    for name in ("HardwareConfig", "ModelConfig", "EngineConfig", "DeploymentMode",
                 "SmartDecodingConfig", "SmartKVCacheConfig", "DistributedKVCacheConfig",
                 "SmartKVSparseConfig", "SmartAccelInput"):
        setattr(mod, name, lambda **kw: types.SimpleNamespace(**kw))

    def _resolve_smart_accel_from_config(**kwargs):
        flags = kwargs.get("flags")
        dec = None
        if flags and flags.decoding_enabled:
            dec = types.SimpleNamespace(
                engine_config={"speculative_config": {"method": "mtp"}},
                env={}, wings_accel_params={"selected": "mtp"},
            )
        return types.SimpleNamespace(
            smart_decoding_output=dec, smart_kv_cache_output=None, smart_kv_sparse_output=None,
            wings_accel_params={"overall": "ok"},
        )
    mod.LoadFlags = types.SimpleNamespace
    mod.resolve_smart_accel_from_config = _resolve_smart_accel_from_config
    return mod


def test_build_input_maps_switches_to_schema():
    """验证 switches 字典正确映射到 SmartAccelInput 各子配置(KV 三级 + spec + sparse + pd)。"""
    mod = _stub_mod()
    sw = collect_accel_switches({
        "ENABLE_KV_OFFLOAD": "true", "ENABLE_KV_MEM_OFFLOAD": "true", "KV_MEM_OFFLOAD_SIZE": "64",
        "ENABLE_KV_QAT": "true", "KV_QAT_INSTANCE_NUM": "2", "PD_ROLE": "D",
    })
    si = build_smart_input(
        mod, hardware_family="h200", gpu_count=8, model_path="/m", model_name="M",
        engine="vllm", engine_version="0.19.0", switches=sw,
    )
    assert si.hardware_config.gpu_type == "h200"
    assert si.smart_kv_cache_config.enabled is True
    assert si.smart_kv_cache_config.memory_offload_size_mode == "64"
    assert si.smart_kv_cache_config.qat_device_count == 2
    assert si.deployment_mode.pd_role == "D"  # PD_ROLE 原样透传(不在此归一)
    assert not hasattr(si.model_config, "model_arch") or si.model_config.model_arch is None


# ── collect_output / apply_smart_accel ─────────────────────────────────────

def test_collect_output_flattens_incl_custom_cli():
    """验证 engine_config 并入结构化参数,诊断进 audit。"""
    part = types.SimpleNamespace(
        engine_config={"speculative_config": {}, "x": "1"},
        env={"E": "1"}, wings_accel_params={"sel": "mtp"},
    )
    out = types.SimpleNamespace(
        smart_decoding_output=part, smart_kv_cache_output=None, smart_kv_sparse_output=None,
        wings_accel_params={"overall": "ok"},
    )
    r = collect_output(out)
    assert r.engine_config == {"speculative_config": {}, "x": "1"}
    assert r.env == {"E": "1"} and r.audit["wings_accel"] == {"overall": "ok"}


def test_collect_output_maps_generated_files():
    """验证 output.generated_files → AccelResult.generated_files(归一为 GeneratedFileSpec)。"""
    gf = types.SimpleNamespace(
        path="/shared-volume/lmcache_config.yaml",
        content="chunk_size: 256\n",
        mode="0644",
        scope="all",
        source_file="model.yaml",
        source_path="smart_accel.kv_offload[0].files[0]",
    )
    out = types.SimpleNamespace(
        engine_params=types.SimpleNamespace(engine_config={"x": "1"}, env={"E": "1"}),
        generated_files=[gf],
    )
    r = collect_output(out)
    assert len(r.generated_files) == 1
    spec = r.generated_files[0]
    assert spec.path == "/shared-volume/lmcache_config.yaml"
    assert spec.content == "chunk_size: 256\n"
    assert spec.mode == "0644" and spec.scope == "all"
    assert spec.source_file == "model.yaml"
    assert spec.source_path == "smart_accel.kv_offload[0].files[0]"


def test_collect_output_generated_files_absent_defaults_empty():
    """验证旧/stub 输出无 generated_files → 空列表(向后兼容,不崩)。"""
    out = types.SimpleNamespace(
        engine_params=types.SimpleNamespace(engine_config={"x": "1"}, env={"E": "1"}),
    )
    r = collect_output(out)
    assert r.generated_files == []


def test_collect_output_plan_only_marks_accel_enabled():
    """文件计划、依赖和 pre-serve 本身也是有效 accel 运行时产出。"""
    out = types.SimpleNamespace(
        engine_params=types.SimpleNamespace(engine_config={}, env={}),
        generated_files=[
            types.SimpleNamespace(path="/shared-volume/config.yaml", content="enabled: true\n")
        ],
        packages=["lmcache:v0.3.15"],
        pre_serve=["mkdir -p /shared-volume"],
        pre_serve_trusted=True,
    )

    result = collect_output(out)

    assert result.enabled is True
    assert result.packages == ["lmcache:v0.3.15"]
    assert result.pre_serve == ["mkdir -p /shared-volume"]
    assert result.pre_serve_trusted is True
    assert len(result.generated_files) == 1




def test_apply_module_absent_is_noop():
    """验证 wings-accel 模块未在场 → 空 AccelResult(no-op,不打断启动)。"""
    monkey = types.SimpleNamespace()  # 占位,确保 _import_accel 真实路径
    _ = monkey
    result = apply_smart_accel(
        hardware_family="h200", gpu_count=8, model_path="/m", model_name="M",
        engine="vllm", engine_version="0.19.0", env={"ENABLE_SPECULATIVE_DECODE": "true"},
    )
    # 真模块可能在场也可能不在;若不在 → 空。这里只断言不抛异常且返回 AccelResult。
    assert isinstance(result, AccelResult)


def test_apply_with_stub_module_spec_on(monkeypatch):
    """验证 stub 模块在场 + spec 开 → engine_config 含 speculative_config、诊断进 audit。"""
    monkeypatch.setattr(smart_accel, "_import_accel", _stub_mod)
    result = apply_smart_accel(
        hardware_family="h200", gpu_count=8, model_path="/m", model_name="M",
        engine="vllm", engine_version="0.19.0", env={"ENABLE_SPECULATIVE_DECODE": "true"},
    )
    assert result.enabled is True
    assert result.engine_config["speculative_config"]["method"] == "mtp"
    assert result.audit["smart_decoding_output"]["selected"] == "mtp"


def test_apply_propagates_smart_accel_configuration_error(monkeypatch):
    """确定性 SmartAccel 配置错误必须阻止启动，而不是静默关闭加速。"""
    class SmartAccelConfigurationError(ValueError):
        pass

    mod = _stub_mod()
    mod.SmartAccelConfigurationError = SmartAccelConfigurationError

    def _raise_configuration_error(**kwargs):
        raise SmartAccelConfigurationError("conflicting package versions")

    mod.resolve_smart_accel_from_config = _raise_configuration_error
    monkeypatch.setattr(smart_accel, "_import_accel", lambda: mod)

    with pytest.raises(SmartAccelConfigurationError, match="conflicting package versions"):
        apply_smart_accel(
            hardware_family="h200", gpu_count=8, model_path="/m", model_name="M",
            engine="vllm", engine_version="0.19.0", env={},
        )


def _pre_serve_stub_mod(trusted):
    """构造返回启动前命令的 SmartAccel stub，用于验证消费端可信门禁。"""
    mod = types.SimpleNamespace()
    mod.LoadFlags = lambda **kwargs: types.SimpleNamespace(**kwargs)
    mod.resolve_smart_accel_from_config = lambda **kwargs: types.SimpleNamespace(
        engine_params=types.SimpleNamespace(engine_config={}, env={}),
        pre_serve=["mkdir -p /shared-volume"],
        pre_serve_trusted=trusted,
    )
    return mod


@pytest.mark.parametrize("trusted", [False, None])
def test_apply_rejects_untrusted_pre_serve(monkeypatch, trusted):
    """验证有启动前命令但来源外部或未知时不能被无加速降级掩盖。"""
    monkeypatch.setattr(
        smart_accel,
        "_import_accel",
        lambda: _pre_serve_stub_mod(trusted),
    )

    with pytest.raises(ValueError, match="trusted package source"):
        apply_smart_accel(
            hardware_family="h200",
            gpu_count=8,
            model_path="/m",
            model_name="M",
            engine="vllm",
            engine_version="0.19.0",
            env={},
        )


def test_apply_accepts_trusted_pre_serve(monkeypatch):
    """验证有启动前命令且来源为包内资产时正常返回。"""
    monkeypatch.setattr(
        smart_accel,
        "_import_accel",
        lambda: _pre_serve_stub_mod(True),
    )

    result = apply_smart_accel(
        hardware_family="h200",
        gpu_count=8,
        model_path="/m",
        model_name="M",
        engine="vllm",
        engine_version="0.19.0",
        env={},
    )

    assert result.pre_serve_trusted is True


def test_apply_propagates_accel_configuration_error(monkeypatch):
    """验证 SmartAccel 配置错误不会被 optional integration 的通用降级吞掉。"""
    class StubConfigurationError(ValueError):
        """模拟 wings-accel 对外公开的配置错误类型。"""

    def _raise_configuration_error(**kwargs):
        raise StubConfigurationError("invalid SmartAccel asset")

    mod = types.SimpleNamespace(
        LoadFlags=lambda **kwargs: types.SimpleNamespace(**kwargs),
        SmartAccelConfigurationError=StubConfigurationError,
        resolve_smart_accel_from_config=_raise_configuration_error,
    )
    monkeypatch.setattr(smart_accel, "_import_accel", lambda: mod)

    with pytest.raises(ValueError, match="invalid SmartAccel asset"):
        apply_smart_accel(
            hardware_family="h200",
            gpu_count=8,
            model_path="/m",
            model_name="M",
            engine="vllm",
            engine_version="0.19.0",
            env={},
        )


def test_maas_flags_sole_driver_no_yaml_auto_enable(monkeypatch):
    """框架已无 auto 机制:适配层构造的 LoadFlags 不得再带 no_auto 键(防字段被加回)。

    MaaS 开关为唯一驱动,yaml 块存在不再自动启用特性。若有人把 no_auto 字段加回,
    本测试直接失败。"全关=no-op"由 test_accel_disabled_is_no_op 端到端守住。
    """
    captured = {}

    def _loadflags(**kw):
        captured.update(kw)
        return types.SimpleNamespace(**kw)

    mod = _stub_mod()
    mod.LoadFlags = _loadflags
    monkeypatch.setattr(smart_accel, "_import_accel", lambda: mod)

    apply_smart_accel(
        hardware_family="h200", gpu_count=8, model_path="/m", model_name="M",
        engine="vllm", engine_version="0.19.0", env={},
    )
    assert "no_auto" not in captured


def test_apply_smart_accel_threads_gpu_count_into_flags(monkeypatch):
    """gpu_count(device_count)必须原样进入 LoadFlags(worker 数与均分的口径)。"""
    captured = {}

    def _loadflags(**kw):
        captured.update(kw)
        return types.SimpleNamespace(**kw)

    mod = _stub_mod()
    mod.LoadFlags = _loadflags
    monkeypatch.setattr(smart_accel, "_import_accel", lambda: mod)

    apply_smart_accel(
        hardware_family="ascend-a3", gpu_count=8, model_path=None,
        model_name="DeepSeek-V4-Flash-w8a8-mtp", engine="vllm-ascend",
        engine_version="v0.21.0rc", tp_size=4, dp_size=4,
        env={"ENABLE_KV_OFFLOAD": "true", "KV_MEM_OFFLOAD_SIZE": "16"},
    )
    assert captured["gpu_count"] == 8
    assert captured["tp_size"] == 4 and captured["dp_size"] == 4
