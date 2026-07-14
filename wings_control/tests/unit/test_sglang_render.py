"""sglang 渲染单测(docs/49):命令规格 build_command_head + param_mapping._SGLANG。"""

from __future__ import annotations

import pytest

from wings_ctl.core.models import SourceEvent, TracedValue
from wings_ctl.engines.vllm_adapter import build_argv, build_command_head
from wings_ctl.translators.param_mapping import translate


def _tv(v):
    """构造最小 TracedValue。"""
    return TracedValue(v, "t", "t.yaml", "t", [SourceEvent("set", "t", v, "t.yaml", "t")])


# ── 命令规格(build_command_head)──────────────────────────────────────────

def test_head_vllm_model_positional():
    """vllm:model 作位置参数,紧跟 `vllm serve`。"""
    assert build_command_head("vllm", "Qwen/Qwen3") == ["vllm", "serve", "Qwen/Qwen3"]


def test_head_sglang_model_named():
    """sglang:启动入口 + model 走 `--model-path`(具名,非位置)。"""
    assert build_command_head("sglang", "/data/DeepSeek-V3") == [
        "python3", "-m", "sglang.launch_server", "--model-path", "/data/DeepSeek-V3",
    ]


def test_head_unknown_engine_raises():
    """未知引擎 → ValueError(Unknown engine)。"""
    with pytest.raises(ValueError, match="Unknown engine"):
        build_command_head("mindie", "x")


# ── param_mapping._SGLANG ─────────────────────────────────────────────────

@pytest.mark.parametrize("key,expected", [
    ("model_path", "model"),                       # 归一 canonical 键
    ("model_name", "served_model_name"),
    ("max_model_len", "context_length"),
    ("max_num_seqs", "max_running_requests"),
    ("max_num_batched_tokens", "chunked_prefill_size"),
    ("gpu_memory_utilization", "mem_fraction_static"),
    ("seed", "random_seed"),
    ("host", "host"),                              # 同名直通(不列 → 缺省返回原名)
    ("port", "port"),
    ("trust_remote_code", "trust_remote_code"),
])
def test_sglang_translate_rename_and_passthrough(key, expected):
    """sglang 改名 + 同名直通:各键翻译成 sglang native。"""
    assert translate(key, "sglang") == expected


@pytest.mark.parametrize("key", [
    "input_length", "output_length", "enable_auto_think_choice",
    "enable_auto_tool_choice", "enable_chunked_prefill", "block_size",
])
def test_sglang_translate_dropped(key):
    """sglang 丢弃项:translate 返回 None(空串=丢弃)。"""
    assert translate(key, "sglang") is None


# ── model / model_path 别名去重(部分 sglang recipe 同时有两键)────────────────

def test_build_argv_model_and_model_path_no_duplicate():
    """recipe 同时有 model + model_path → 只渲染一次 --model-path(不重复)。"""
    argv = build_argv({"model": _tv("poolside/Laguna"), "model_path": _tv("poolside/Laguna"),
                       "tp": _tv(4)}, engine="sglang")
    assert argv.count("--model-path") == 1
    assert "poolside/Laguna" in argv


def test_build_argv_only_model_path_alias():
    """recipe 仅有 model_path(无 model)→ 别名回退,正常渲染 --model-path。"""
    argv = build_argv({"model_path": _tv("X"), "tp": _tv(4)}, engine="sglang")
    assert argv[:5] == ["python3", "-m", "sglang.launch_server", "--model-path", "X"]


def test_build_argv_vllm_model_path_key_unaffected_positional():
    """vllm:model 仍位置参数;model_path 别名也归一(不会冒出 --model-path)。"""
    argv = build_argv({"model": _tv("Q/M"), "tensor_parallel_size": _tv(8)}, engine="vllm")
    assert argv[:3] == ["vllm", "serve", "Q/M"]
    assert "--model-path" not in argv
