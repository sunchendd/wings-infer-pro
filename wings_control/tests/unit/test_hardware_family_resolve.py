"""hardware_family 归一解析单测:显存后缀解析/剥离 + resolve_family_dir 别名/精确/剥后缀/失败。

覆盖 docs/54 §2 的目录解析机制:下发的 resourceCardName(+ 显存后缀、大小写不一)
→ 实际 config 目录名。用真实 config 资产(config_root_real)断言。
"""

from __future__ import annotations

import logging

import pytest

from wings_ctl.hardware.resolver import parse_gpu_mem_suffix, strip_gpu_mem_suffix
from wings_ctl.loaders import locator
from wings_ctl.loaders.locator import resolve_family_dir


# ─── 显存后缀解析 / 剥离 ──────────────────────────────────────────────

def test_parse_gpu_mem_suffix_basic():
    """带 _<N>G 后缀 → 解析出整数 GB。"""
    assert parse_gpu_mem_suffix("H100_80G") == 80


def test_parse_gpu_mem_suffix_case_insensitive():
    """后缀大小写无关(config 变体目录用大写 G)。"""
    assert parse_gpu_mem_suffix("h20_96g") == 96


def test_parse_gpu_mem_suffix_none_when_absent():
    """无后缀(普通卡裸名)→ None。"""
    assert parse_gpu_mem_suffix("gb200") is None


def test_parse_gpu_mem_suffix_not_misfire_on_non_suffix():
    """结尾不是 _<数字>G 的不误伤(gb200 结尾 200,无尾随 G)。"""
    assert parse_gpu_mem_suffix("dgx_station_gb300") is None


def test_strip_gpu_mem_suffix_removes_only_tail():
    """剥后缀只去尾部 _<N>G,得卡型基名;无后缀原样返回。"""
    assert strip_gpu_mem_suffix("H100_80G") == "H100"
    assert strip_gpu_mem_suffix("gb200") == "gb200"


# ─── resolve_family_dir(真实 config 资产)────────────────────────────

def test_resolve_family_dir_exact_bare(config_root_real):
    """裸名精确命中普通目录(gb200 → gb200)。"""
    assert resolve_family_dir(config_root_real, "vllm", "gb200", "", False) == "gb200"


def test_resolve_family_dir_strip_normal_card(config_root_real):
    """普通卡带冗余显存后缀 → 剥后缀命中裸目录(H100_80G → h100)。"""
    assert resolve_family_dir(config_root_real, "vllm", "H100_80G", "", False) == "h100"


def test_resolve_family_dir_exact_variant(config_root_real):
    """显存敏感卡精确命中带后缀目录(h20_96G → h20_96G,不剥后缀)。"""
    assert resolve_family_dir(config_root_real, "vllm", "h20_96G", "", False) == "h20_96G"


def test_resolve_family_dir_casefold_variant(config_root_real):
    """大小写无关:h20_96g 归一后仍命中大写 G 的真实目录 h20_96G。"""
    assert resolve_family_dir(config_root_real, "vllm", "h20_96g", "", False) == "h20_96G"


def test_resolve_family_dir_unknown_card_fail_fast(config_root_real):
    """无对应资产的卡(虚构卡型)→ fail-fast，不静默兜底。
    """
    with pytest.raises(FileNotFoundError, match="无配置资产"):
        resolve_family_dir(config_root_real, "vllm", "NonExistentCard_99G", "", False)


def test_resolve_family_dir_alias_takes_precedence(config_root_real, monkeypatch):
    """别名表命中(卡名≠目录名)→ 用别名目标,优先于精确/剥后缀。"""
    monkeypatch.setitem(locator._ALIAS, "mycard", "gb200")
    assert resolve_family_dir(config_root_real, "vllm", "MyCard_80G", "", False) == "gb200"


def test_resolve_family_dir_alias_bad_target_warns_and_fallthrough(config_root_real, monkeypatch, caplog):
    """别名目标目录不存在(_ALIAS 配错)→ 记 WARNING 且回落;此例回落剥后缀命中 h100。"""
    monkeypatch.setitem(locator._ALIAS, "h100", "nonexistent-dir")
    with caplog.at_level(logging.WARNING):
        result = resolve_family_dir(config_root_real, "vllm", "H100_80G", "", False)
    assert result == "h100"  # 别名目标缺失 → 回落剥后缀命中
    assert "别名" in caplog.text and "nonexistent-dir" in caplog.text
