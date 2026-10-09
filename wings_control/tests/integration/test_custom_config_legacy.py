"""集成测试 — FOAI 旧版前端自定义 JSON 模板过渡适配(legacy_json_adapter)。

覆盖(核心理念:适配层产出 = 用户直接传的新版参数):
(a) vllm/vllm-ascend:长度求和→max_model_len;tp 未填补 device_count;enable_auto_think_choice
    丢弃;其余 vllm 原生键透传;input/output-length 不残留
(b) vllm:用户基于模板添加的未知键一律透传
(c) sglang:长度求和→context_length;四次映射;六个非原生键丢弃;原生透传;input/output-length 不残留
(d) sglang:用户添加键透传
(e) 权威长度键已填 → 透传并丢弃 length 源(不生成 input+output)
(f) 未填权威长度键但只填一侧 input/output = 记 0;两侧都未填 = 不生成
(g) 用户已填 tensor-parallel-size → 以用户为准
(h) 对侧长度键(vllm 填 context_length)→ 透传(用户自添)
(i) mindie(不支持)不干预,原样透传
(j) 丢弃项进 config_file_dropped 审计(带 legacy_json_adapter reason)
"""

from __future__ import annotations

import os

from wings_ctl.core.config_resolver import resolve_custom_config
from wings_ctl.core.models import (
    CustomConfigFile,
    EngineVersion,
    ResolvedEnv,
    Target,
    UserInput,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.version_resolver import resolve_engine_version
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.hardware.resolver import resolve_hardware

# FOAI 旧版前端模板的 params(与设计文档的示例一致)。
LEGACY_PARAMS = {
    "input-length": 2048,
    "output-length": 2048,
    "trust-remote-code": True,
    "dtype": "auto",
    "kv-cache-dtype": "auto",
    "gpu-memory-utilization": 0.8,
    "enable-chunked-prefill": True,
    "block-size": 16,
    "max-num-seqs": 32,
    "max-num-batched-tokens": 4096,
    "seed": 42,
    "enable-expert-parallel": False,
    "enable-prefix-caching": True,
    "enable-auto-tool-choice": False,
    "enable-auto-think-choice": False,
}

CLI_OVERRIDES = {"model": "/weights/MiniMax-M3-MXFP8", "served_model_name": "MiniMax-M3-MXFP8"}


def _env(config_root, hardware_info_path, *, engine: str = "vllm") -> ResolvedEnv:
    os.environ["ENGINE_VERSION"] = "0.19.0"
    try:
        hardware = resolve_hardware(hardware_info_path)
        if engine == "sglang":
            engine_version = EngineVersion(
                requested="v0.5.10",
                resolved="v0.5.10",
                is_fallback=False,
                has_version_dir=True,
            )
            return ResolvedEnv(
                config_root=config_root,
                hardware=hardware,
                engine_version=engine_version,
            )
        engine_version = resolve_engine_version(
            config_root, hardware.hardware_family, engine=engine
        )
        return ResolvedEnv(config_root=config_root, hardware=hardware, engine_version=engine_version)
    finally:
        os.environ.pop("ENGINE_VERSION", None)


def _resolve(config_root, hardware_info_path, *, engine="vllm", params=None, device_count=2):
    return resolve_custom_config(
        _env(config_root, hardware_info_path, engine=engine),
        Target(model_name="MiniMax-M3-MXFP8", topology=Topology.STANDALONE, engine=engine),
        config_file=CustomConfigFile(params=params if params is not None else dict(LEGACY_PARAMS)),
        user_input=UserInput(cli_overrides=CLI_OVERRIDES),
        device_count=device_count,
    )


def _dropped_keys(resolved) -> set:
    return {d["key"] for d in resolved.config_file_params if d["status"] == "dropped"}


# ─── (a) vllm/vllm-ascend ───


def test_a_vllm_legacy_mapping(config_root, hardware_info_path):
    """vllm:长度求和→max_model_len;tp 补 device_count;auto_think 丢弃;原生透传;length 源不残留。"""
    for engine in ("vllm", "vllm-ascend"):
        resolved = _resolve(config_root, hardware_info_path, engine=engine, device_count=2)
        tr = resolved.engine_config_traces

        # 长度求和 input+output = 4096 → max_model_len
        assert tr["max_model_len"].final_value == 4096
        # tp 未填 → 补 device_count
        assert tr["tensor_parallel_size"].final_value == 2
        # vllm 原生键透传
        assert tr["trust_remote_code"].final_value is True
        assert tr["gpu_memory_utilization"].final_value == 0.8
        assert tr["enable_chunked_prefill"].final_value is True
        assert tr["enable_prefix_caching"].final_value is True
        assert tr["enable_auto_tool_choice"].final_value is False
        # 旧模板业务键 input/output-length 不入 traces(已合并为 max_model_len,不残留)
        assert "input_length" not in tr
        assert "output_length" not in tr
        # enable_auto_think_choice(vllm 非原生)被丢弃 + 审计
        assert "enable_auto_think_choice" not in tr
        assert "enable_auto_think_choice" in _dropped_keys(resolved)


def test_a1_vllm_authoritative_len_passthrough(config_root, hardware_info_path):
    """vllm:已填权威长度键 max_model_len → 透传,丢弃 length 源(不覆盖为 input+output)。"""
    params = dict(LEGACY_PARAMS)
    params["max_model_len"] = 16000
    resolved = _resolve(config_root, hardware_info_path, engine="vllm", params=params)
    tr = resolved.engine_config_traces
    assert tr["max_model_len"].final_value == 16000
    assert "input_length" not in tr
    assert "output_length" not in tr


def test_a2_vllm_opposite_len_passthrough(config_root, hardware_info_path):
    """vllm:对侧长度键 context_length → 用户自添,透传(引擎报错兜底);仍正常生成 max_model_len。"""
    params = dict(LEGACY_PARAMS)
    params["context_length"] = 7777
    resolved = _resolve(config_root, hardware_info_path, engine="vllm", params=params)
    tr = resolved.engine_config_traces
    assert tr["context_length"].final_value == 7777
    assert tr["max_model_len"].final_value == 4096


# ─── (b) vllm 用户添加键透传 ───


def test_a3_vllm_ascend_gpu_usage_mode_enpu_translates_to_enforce_eager(
    config_root, hardware_info_path
):
    params = dict(LEGACY_PARAMS)
    params["gpu-usage-mode"] = "enpu"

    resolved = _resolve(
        config_root,
        hardware_info_path,
        engine="vllm-ascend",
        params=params,
    )
    argv = build_argv(resolved.engine_config_traces, engine="vllm-ascend")

    assert resolved.engine_config_traces["enforce_eager"].final_value is True
    assert "gpu_usage_mode" not in resolved.engine_config_traces
    assert "--enforce-eager" in argv
    assert "--gpu-usage-mode" not in argv
    assert "gpu_usage_mode" in _dropped_keys(resolved)


def test_b_vllm_user_added_passthrough(config_root, hardware_info_path):
    """用户基于模板添加的未知键 → vllm 一律透传(不映射不丢弃)。"""
    params = dict(LEGACY_PARAMS)
    params["my_custom_flag"] = 8192
    resolved = _resolve(config_root, hardware_info_path, engine="vllm", params=params)
    tr = resolved.engine_config_traces
    assert tr["my_custom_flag"].final_value == 8192
    assert "my_custom_flag" not in _dropped_keys(resolved)


# ─── (c) sglang 映射/丢弃/透传 ───


def test_c_sglang_legacy_mapping(config_root, hardware_info_path):
    """sglang:长度求和→context_length;四次映射;非原生丢弃;原生透传;length 源不残留。"""
    engine = "sglang"
    resolved = _resolve(config_root, hardware_info_path, engine=engine, device_count=2)
    tr = resolved.engine_config_traces

    # 长度求和 → context_length
    assert tr["context_length"].final_value == 4096
    # 四次映射
    assert tr["max_running_requests"].final_value == 32
    assert tr["chunked_prefill_size"].final_value == 4096
    assert tr["mem_fraction_static"].final_value == 0.8
    assert tr["random_seed"].final_value == 42
    # sglang 原生透传
    assert tr["trust_remote_code"].final_value is True
    # 长度源不残留
    assert "input_length" not in tr
    assert "output_length" not in tr
    # 丢弃的旧键不入 traces
    for dropped_key in (
        "enable_chunked_prefill",
        "block_size",
        "enable_expert_parallel",
        "enable_prefix_caching",
        "enable_auto_tool_choice",
        "enable_auto_think_choice",
        "gpu_memory_utilization",
        "max_num_seqs",
        "max_num_batched_tokens",
        "seed",
    ):
        assert dropped_key not in tr, f"{dropped_key} 应被丢弃"
    dropped = _dropped_keys(resolved)
    assert {
        "enable_chunked_prefill", "block_size", "enable_expert_parallel",
        "enable_prefix_caching", "enable_auto_tool_choice", "enable_auto_think_choice",
    } <= dropped


def test_c1_sglang_authoritative_len_passthrough(config_root, hardware_info_path):
    """sglang:已填权威长度键 context_length → 透传并丢弃 length 源。"""
    params = dict(LEGACY_PARAMS)
    params["context_length"] = 9999
    resolved = _resolve(config_root, hardware_info_path, engine="sglang", params=params)
    tr = resolved.engine_config_traces
    assert tr["context_length"].final_value == 9999
    assert "input_length" not in tr
    assert "output_length" not in tr


# ─── (d) sglang 用户添加键透传 ───


def test_d_sglang_user_added_passthrough(config_root, hardware_info_path):
    """用户基于模板添加的未知键 → sglang 一律透传。"""
    params = dict(LEGACY_PARAMS)
    params["foo_custom"] = "bar"
    resolved = _resolve(config_root, hardware_info_path, engine="sglang", params=params)
    tr = resolved.engine_config_traces
    assert tr["foo_custom"].final_value == "bar"
    assert "foo_custom" not in _dropped_keys(resolved)


# ─── (e)(f) 长度键缺失场景 ───


def test_e_omit_input_output_skips_len(config_root, hardware_info_path):
    """未填权威长度键,且 input/output 都未填 → 不做长度处理。"""
    params = {k: v for k, v in LEGACY_PARAMS.items() if k not in ("input-length", "output-length")}

    vllm_resolved = _resolve(config_root, hardware_info_path, engine="vllm", params=params)
    assert "max_model_len" not in vllm_resolved.engine_config_traces

    sglang_resolved = _resolve(config_root, hardware_info_path, engine="sglang", params=params)
    assert "context_length" not in sglang_resolved.engine_config_traces


def test_f_single_side_len_counts_zero(config_root, hardware_info_path):
    """未填权威长度键,只填一侧 input/output → 缺失侧记 0,max_model_len=已填侧。"""
    params = dict(LEGACY_PARAMS)
    del params["output-length"]  # 只留 input-length=2048
    vllm_resolved = _resolve(config_root, hardware_info_path, engine="vllm", params=params)
    assert vllm_resolved.engine_config_traces["max_model_len"].final_value == 2048

    sglang_resolved = _resolve(config_root, hardware_info_path, engine="sglang", params=params)
    assert sglang_resolved.engine_config_traces["context_length"].final_value == 2048


# ─── (g) tp 已填以用户为准 ───


def test_g_user_filled_tp_respected(config_root, hardware_info_path):
    """用户已填 tensor-parallel-size → 以用户为准(不覆盖为 device_count)。"""
    params = dict(LEGACY_PARAMS)
    params["tensor-parallel-size"] = 8
    resolved = _resolve(config_root, hardware_info_path, engine="vllm", params=params, device_count=2)
    assert resolved.engine_config_traces["tensor_parallel_size"].final_value == 8


# ─── (i) mindie(不支持)不干预 ───


def test_i_mindie_not_intervened(config_root, hardware_info_path):
    """mindie 非 vllm/sglang → 适配层不干预,原样透传。"""
    resolved = _resolve(config_root, hardware_info_path, engine="mindie")
    tr = resolved.engine_config_traces
    assert tr["input_length"].final_value == 2048
    assert tr["output_length"].final_value == 2048
    assert not _dropped_keys(resolved)


# ─── (j) 丢弃项进审计 ───


def test_j_legacy_drop_has_reason(config_root, hardware_info_path):
    """丢弃项进 config_file_dropped 审计,带 legacy_json_adapter reason。"""
    resolved = _resolve(config_root, hardware_info_path, engine="sglang", device_count=2)
    drop_entries = [
        d
        for d in resolved.config_file_params
        if d["status"] == "dropped" and d["key"] in ("enable_chunked_prefill", "block_size")
    ]
    assert len(drop_entries) == 2
    assert all("legacy_json_adapter" in (d["reason"] or "") for d in drop_entries)


# ─── (k) custom 路径 accel 开关短路(基础修复) ───


def test_k_custom_no_accel_no_hardware_lookup(config_root, hardware_info_path):
    """未开启加速特性 → custom 不定位硬件资产(sglang 无该资产也不报错),accel 层为空。"""
    # 确保无 accel 开关泄漏(防测试环境残留)。
    for k in os.environ:
        if k.startswith("ENABLE_") and k != "ENGINE_VERSION":
            os.environ.pop(k, None)
    # sglang 在本 fixture 无 nvidia-RTX5880 硬件资产;未开 accel 时必须能跑通(不 fail-fast)。
    resolved = _resolve(config_root, hardware_info_path, engine="sglang", device_count=2)
    # accel 未开启 → 无 strategy_accel 层 / strategy_accel_env 层
    assert (
        resolved.engine_config_traces["context_length"].final_layer != "strategy_accel"
    )


def test_k1_custom_sglang_accel_is_dropped(
    config_root, hardware_info_path, monkeypatch, caplog
):
    """SGLang custom 路径也应忽略 accel 开关，不定位 accel 资产。"""
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")

    resolved = _resolve(config_root, hardware_info_path, engine="sglang", device_count=2)

    assert resolved.accel.enabled is False
    assert resolved.resolution_notes["accel_policy"] == "drop_warn"
    assert (
        resolved.resolution_notes["accel_dropped_switches"]
        == "ENABLE_SPECULATIVE_DECODE"
    )
    assert "ignored switches: ENABLE_SPECULATIVE_DECODE" in caplog.text
