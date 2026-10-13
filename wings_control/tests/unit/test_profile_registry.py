"""profile 注册表核心逻辑单测（registry.md §4）。

覆盖：各 key 的 match 语义、偏序裁决（hardware 集合包含 / context_length 区间包含）、
等价/互不偏序报歧义、未注册 key / 必填缺失处理。
"""

from __future__ import annotations

import pytest

from wings_ctl.loaders.profile_registry import (
    PROFILE_KEYS,
    ProfileAmbiguityError,
    evaluate_profile,
    is_more_specific,
    resolve,
)


# ── 注册表结构 ──────────────────────────────────────────────────────────────

def test_registry_contains_expected_keys():
    assert set(PROFILE_KEYS) == {
        "engine",
        "model",
        "version",
        "hardware",
        "context_length",
        "cpu_arch",
    }


def test_required_and_partial_order_flags():
    for key in ("engine", "model", "version"):
        assert PROFILE_KEYS[key].required is True
        assert PROFILE_KEYS[key].partial_order is False
    assert PROFILE_KEYS["hardware"].required is True
    assert PROFILE_KEYS["hardware"].partial_order is True
    assert PROFILE_KEYS["context_length"].required is False
    assert PROFILE_KEYS["context_length"].partial_order is True
    assert PROFILE_KEYS["cpu_arch"].required is False
    assert PROFILE_KEYS["cpu_arch"].partial_order is True


# ── match 语义 ──────────────────────────────────────────────────────────────

def _ctx(**overrides):
    base = {"engine": "vllm", "version": "v0.30.0", "hardware": "h20_141G", "model": "DeepSeek-V3"}
    base.update(overrides)
    return base


def test_engine_match_casefold_and_underscore():
    profile = {"engine": "VLLM_Ascend", "model": "m", "version": "v", "hardware": {"a"}}
    assert evaluate_profile(profile, {"engine": "vllm-ascend", "model": "m", "version": "v", "hardware": "a"})


def test_version_prefix_match():
    profile = {"engine": "vllm", "model": "m", "version": "v0.23", "hardware": {"h"}}
    assert evaluate_profile(profile, {"engine": "vllm", "model": "m", "version": "v0.23.0", "hardware": "h"})
    assert not evaluate_profile(profile, {"engine": "vllm", "model": "m", "version": "v0.30.0", "hardware": "h"})


def test_hardware_set_membership_casefold():
    profile = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h20_141G", "H20_96G"}}
    assert evaluate_profile(profile, {"engine": "vllm", "model": "m", "version": "v", "hardware": "h20_141G"})
    assert not evaluate_profile(profile, {"engine": "vllm", "model": "m", "version": "v", "hardware": "h100"})


def test_hardware_yaml_flow_mapping_as_set():
    # YAML `hardware: {b200, B200}` 解析为 dict {"b200": None, "B200": None}
    profile = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"b200": None, "B200": None}}
    assert evaluate_profile(profile, {"engine": "vllm", "model": "m", "version": "v", "hardware": "b200"})


def test_cpu_arch_set_membership_casefold():
    profile = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}, "cpu_arch": {"aarch64", "x86_64"}}
    assert evaluate_profile(
        profile, {"engine": "vllm", "model": "m", "version": "v", "hardware": "h", "cpu_arch": "AArch64"}
    )
    assert not evaluate_profile(
        profile, {"engine": "vllm", "model": "m", "version": "v", "hardware": "h", "cpu_arch": "ppc64le"}
    )


def test_cpu_arch_yaml_flow_mapping_as_set():
    # YAML `cpu_arch: {aarch64, x86_64}` 解析为 dict {"aarch64": None, "x86_64": None}
    profile = {
        "engine": "vllm",
        "model": "m",
        "version": "v",
        "hardware": {"h"},
        "cpu_arch": {"aarch64": None, "x86_64": None},
    }
    assert evaluate_profile(
        profile, {"engine": "vllm", "model": "m", "version": "v", "hardware": "h", "cpu_arch": "x86_64"}
    )


def test_cpu_arch_ctx_missing_rejected():
    profile = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}, "cpu_arch": {"aarch64"}}
    assert not evaluate_profile(profile, _ctx())  # ctx 无 cpu_arch


def test_context_length_inequality():
    profile = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}, "context_length": {">=": 131072}}
    ctx = {"engine": "vllm", "model": "m", "version": "v", "hardware": "h", "context_length": 200000}
    assert evaluate_profile(profile, ctx)
    assert not evaluate_profile(profile, {**ctx, "context_length": 100000})


def test_context_length_scalar_exact():
    profile = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}, "context_length": 131072}
    ctx = {"engine": "vllm", "model": "m", "version": "v", "hardware": "h", "context_length": 131072}
    assert evaluate_profile(profile, ctx)
    assert not evaluate_profile(profile, {**ctx, "context_length": 131073})


def test_context_length_in():
    profile = {
        "engine": "vllm",
        "model": "m",
        "version": "v",
        "hardware": {"h"},
        "context_length": {"in": [131072, 262144]},
    }
    ctx = {"engine": "vllm", "model": "m", "version": "v", "hardware": "h", "context_length": 262144}
    assert evaluate_profile(profile, ctx)
    assert not evaluate_profile(profile, {**ctx, "context_length": 100000})


# ── 必填缺失 / 未注册 key / ctx 缺值 ───────────────────────────────────────

def test_missing_required_key_rejected():
    profile = {"engine": "vllm", "model": "m", "version": "v"}  # 缺 hardware
    assert not evaluate_profile(profile, _ctx())


def test_unregistered_key_rejected():
    profile = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}, "dtype": "bf16"}
    assert not evaluate_profile(profile, {**_ctx(), "dtype": "bf16"})


def test_ctx_missing_optional_key_rejected():
    profile = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}, "context_length": {">=": 1}}
    assert not evaluate_profile(profile, _ctx())  # ctx 无 context_length


def test_invalid_profile_value_tolerated():
    # 非法 profile 值（hardware 非集合/列表/字符串）→ 宽容跳过，不抛错（registry.md §5）。
    profile = {"engine": "vllm", "model": "m", "version": "v", "hardware": 123}
    assert not evaluate_profile(profile, _ctx())


# ── 偏序：hardware 集合包含 ────────────────────────────────────────────────

def _hw_profile(hw):
    return {"engine": "vllm", "model": "m", "version": "v", "hardware": hw}


def test_hardware_specificity():
    generic = _hw_profile({"h20_96G", "h20_141G"})
    specific = _hw_profile({"h20_141G"})
    assert is_more_specific(specific, generic)
    assert not is_more_specific(generic, specific)
    assert not is_more_specific(specific, _hw_profile({"h20_141G"}))  # 等价


# ── 偏序：cpu_arch 集合包含 ────────────────────────────────────────────────

def _arch_profile(arch):
    return {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}, "cpu_arch": arch}


def test_cpu_arch_specificity():
    generic = _arch_profile({"aarch64", "x86_64"})
    specific = _arch_profile({"x86_64"})
    assert is_more_specific(specific, generic)
    assert not is_more_specific(generic, specific)
    assert not is_more_specific(specific, _arch_profile({"x86_64"}))  # 等价


def test_cpu_arch_undeclared_is_most_generic():
    """未声明 cpu_arch 视为最泛化（全集），写了 cpu_arch 的资产更特化。"""
    undeclared = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}}
    specific = _arch_profile({"x86_64"})
    assert is_more_specific(specific, undeclared)
    assert not is_more_specific(undeclared, specific)
    assert not is_more_specific(undeclared, dict(undeclared))


# ── 偏序：context_length 区间包含 ──────────────────────────────────────────

def _cl_profile(cl):
    return {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}, "context_length": cl}


def test_context_length_specificity():
    wide = _cl_profile({">=": 80})
    narrow = _cl_profile({">=": 141})
    assert is_more_specific(narrow, wide)
    assert not is_more_specific(wide, narrow)
    exact = _cl_profile(141)
    assert is_more_specific(exact, wide)


def test_context_length_undeclared_is_most_generic():
    """未声明 context_length 视为最泛化（全集），而非互不偏序。

    不写 context_length 的资产匹配集合 = 全集；任何写了 context_length 的资产
    匹配集合 ⊆ 全集，故后者更特化。这样"不写"天然兜底，不会与"写了"互不偏序。
    """
    undeclared = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}}
    wide = _cl_profile({">=": 0})
    narrow = _cl_profile({">=": 131072})
    # 写了 context_length 的比不写的更特化
    assert is_more_specific(wide, undeclared)
    assert is_more_specific(narrow, undeclared)
    assert not is_more_specific(undeclared, wide)
    assert not is_more_specific(undeclared, narrow)
    # 两个都不写 → 等价（互不更特化）
    assert not is_more_specific(undeclared, dict(undeclared))
    assert not is_more_specific(dict(undeclared), undeclared)


def test_resolve_undeclared_context_length_falls_back_to_most_generic():
    """ctx 有 context_length 时，resolve 取最特化者；不写 context_length 的资产兜底。"""
    undeclared = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}}
    wide = _cl_profile({">=": 0})
    narrow = _cl_profile({">=": 131072})
    ctx = {"engine": "vllm", "model": "m", "version": "v", "hardware": "h", "context_length": 200000}
    # 长上下文 → 最特化的 narrow 胜出
    assert resolve([undeclared, wide, narrow], ctx) == narrow
    # 短上下文（< 131072）→ wide 胜出（narrow 不命中）
    ctx_short = {**ctx, "context_length": 4096}
    assert resolve([undeclared, wide, narrow], ctx_short) == wide


def test_resolve_undeclared_context_length_ctx_missing():
    """ctx 无 context_length 时，只有不写 context_length 的资产命中。"""
    undeclared = {"engine": "vllm", "model": "m", "version": "v", "hardware": {"h"}}
    wide = _cl_profile({">=": 0})
    ctx = {"engine": "vllm", "model": "m", "version": "v", "hardware": "h"}
    # wide 声明了 context_length，ctx 缺值 → 不命中；undeclared 命中
    assert resolve([undeclared, wide], ctx) == undeclared


# ── resolve 裁决 ───────────────────────────────────────────────────────────

def test_resolve_picks_most_specific():
    generic = _hw_profile({"h20_96G", "h20_141G"})
    specific = _hw_profile({"h20_141G"})
    ctx = {"engine": "vllm", "model": "m", "version": "v0.30.0", "hardware": "h20_141G"}
    assert resolve([generic, specific], ctx) == specific


def test_resolve_equivalent_raises_ambiguity():
    specific = _hw_profile({"h20_141G"})
    ctx = {"engine": "vllm", "model": "m", "version": "v", "hardware": "h20_141G"}
    with pytest.raises(ProfileAmbiguityError):
        resolve([specific, dict(specific)], ctx)


def test_resolve_incomparable_raises_ambiguity():
    a = _cl_profile({">=": 100})
    b = _cl_profile({"<=": 200})
    ctx = {"engine": "vllm", "model": "m", "version": "v", "hardware": "h", "context_length": 150}
    with pytest.raises(ProfileAmbiguityError):
        resolve([a, b], ctx)


def test_context_length_opposite_bounds_not_subset():
    """下界区间与上界区间互不包含（`>=100` ⊄ `<=200`，反之亦然）。"""
    lower = _cl_profile({">=": 100})
    upper = _cl_profile({"<=": 200})
    assert not is_more_specific(lower, upper)
    assert not is_more_specific(upper, lower)


def test_context_length_ray_vs_finite_incomparable():
    """回归：下界射线（无限集）不得被判为 ⊆ 有限集（`in`）。

    旧实现 `_covers_lower/_covers_upper` 在 other 无对应界时直接返回 True，
    使 `>=100` 被误判为 ⊆ `in [50,100,200]`，resolve 会错误地淘汰有限集、选中 `>=100`。
    正确语义：两者互不包含 → 互不偏序 → 报歧义。
    """
    ray = _cl_profile({">=": 100})
    finite = _cl_profile({"in": [50, 100, 200]})
    assert not is_more_specific(ray, finite)
    assert not is_more_specific(finite, ray)
    ctx = {"engine": "vllm", "model": "m", "version": "v", "hardware": "h", "context_length": 100}
    with pytest.raises(ProfileAmbiguityError):
        resolve([ray, finite], ctx)


def test_resolve_no_match_raises_ambiguity():
    generic = _hw_profile({"h20_96G", "h20_141G"})
    ctx = {"engine": "vllm", "model": "m", "version": "v", "hardware": "h100"}
    with pytest.raises(ProfileAmbiguityError):
        resolve([generic], ctx)
