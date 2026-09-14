"""hardware_family 归一解析单测:显存后缀解析/剥离 + resolve_family_dir 别名/精确/剥后缀/失败。

覆盖 docs/54 §2 的目录解析机制:下发的 resourceCardName(+ 显存后缀、大小写不一)
→ 实际 config 目录名。用真实 config 资产(config_root_real)断言。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from wings_ctl.hardware.resolver import parse_gpu_mem_suffix, strip_gpu_mem_suffix
from wings_ctl.loaders import locator
from wings_ctl.loaders.locator import build_models_dir, resolve_family_dir


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


def test_resolve_family_dir_exact_variant_not_eaten_by_alias(config_root_real):
    """回归:同型号多显存档(h20_96G / h20_141G)按显存精确命中,不被 _ALIAS['h20']→'h20_96G' 吞掉。

    _ALIAS['h20'] 是给裸卡型 'h20' 做默认档兜底的;下发值带显存后缀时必须按显存精确命中
    对应目录,否则 h20_141G 会被错误坍缩到 h20_96G,用错 recipe(参见 locator.resolve_family_dir)。
    """
    assert resolve_family_dir(config_root_real, "vllm", "h20_141G", "", False) == "h20_141G"
    # 裸卡型仍走别名默认档,语义不变。
    assert resolve_family_dir(config_root_real, "vllm", "h20", "", False) == "h20_96G"


def test_resolve_family_dir_casefold_variant(config_root_real):
    """大小写无关:h20_96g 归一后仍命中大写 G 的真实目录 h20_96G。"""
    assert resolve_family_dir(config_root_real, "vllm", "h20_96g", "", False) == "h20_96G"


def test_resolve_family_dir_unknown_card_fail_fast(config_root_real):
    """默认调用保持严格模式：无对应资产的卡仍 fail-fast。"""
    with pytest.raises(FileNotFoundError, match="No configuration assets"):
        resolve_family_dir(config_root_real, "vllm", "NonExistentCard_99G", "", False)


def test_generic_directory_is_not_a_user_selectable_hardware(config_root_real):
    """保底目录只能由 fallback 选择，不能伪装成正常硬件输入。"""
    with pytest.raises(FileNotFoundError, match="No configuration assets"):
        resolve_family_dir(config_root_real, "vllm", "_generic", "", False)


def test_resolve_family_dir_unknown_card_uses_generic_when_enabled(config_root_real, caplog):
    """普通 recipe 路径可显式启用未知硬件的通用保底目录。"""
    with caplog.at_level(logging.WARNING):
        resolved = resolve_family_dir(
            config_root_real,
            "vllm",
            "NonExistentCard_99G",
            "",
            False,
            allow_generic=True,
        )

    assert resolved == "_generic"
    assert "generic best-effort hardware recipe" in caplog.text


def test_generic_fallback_requires_default_model_file(tmp_path: Path):
    """空的 models 目录不是有效 generic 资产。"""
    (tmp_path / "engines" / "demo" / "_generic" / "models").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="No configuration assets"):
        resolve_family_dir(
            tmp_path,
            "demo",
            "Unknown_1G",
            "",
            False,
            allow_generic=True,
        )


def test_generic_fallback_accepts_default_model_file(tmp_path: Path):
    """generic fallback 的存在性契约以 default_model.yaml 文件为准。"""
    default_model = tmp_path / "engines" / "demo" / "_generic" / "models" / "default_model.yaml"
    default_model.parent.mkdir(parents=True)
    default_model.write_text("scenarios: {}\n", encoding="utf-8")

    assert resolve_family_dir(
        tmp_path,
        "demo",
        "Unknown_1G",
        "",
        False,
        allow_generic=True,
    ) == "_generic"


def test_versioned_engine_generic_path_is_shared_across_versions(config_root_real):
    """版本化引擎的 generic 目录不拼接版本，新版本无需复制保底资产。"""
    expected = config_root_real / "engines" / "vllm-ascend" / "_generic" / "models"

    assert build_models_dir(config_root_real, "vllm-ascend", "_generic", "v0.18.0", True) == expected
    assert build_models_dir(config_root_real, "vllm-ascend", "_generic", "v9.9.9", True) == expected


def test_versioned_engine_unknown_card_uses_shared_generic(config_root_real):
    """具体版本目录无对应硬件时，定位引擎根目录的共享 generic。"""
    assert (
        resolve_family_dir(
            config_root_real,
            "vllm-ascend",
            "NonExistentCard_99G",
            "v0.23.0",
            True,
            allow_generic=True,
        )
        == "_generic"
    )


def test_resolve_family_dir_alias_after_exact_miss(config_root_real, monkeypatch):
    """完整硬件名精确未命中后,别名仍可映射带显存后缀的卡名到目标目录。"""
    monkeypatch.setitem(locator._ALIAS, "mycard", "gb200")
    assert resolve_family_dir(config_root_real, "vllm", "MyCard_80G", "", False) == "gb200"


def test_resolve_family_dir_suffix_bearing_ascend_alias(config_root_real, monkeypatch):
    """回归:非 x86_64 上带显存后缀的昇腾卡名经别名命中架构目录。"""
    monkeypatch.setattr(locator.platform, "machine", lambda: "aarch64")
    assert (
        resolve_family_dir(config_root_real, "vllm-ascend", "Ascend910B_64G", "v0.18.0", True)
        == "ascend-a2"
    )


def test_resolve_family_dir_ascend910b_x86_64_variant(config_root_real, monkeypatch):
    """910B 在 x86_64 上优先使用专属硬件目录。"""
    monkeypatch.setattr(locator.platform, "machine", lambda: "x86_64")
    assert (
        resolve_family_dir(config_root_real, "vllm-ascend", "ascend910b", "v0.23.0", True)
        == "ascend910b-x86_64"
    )


def test_resolve_family_dir_910b_non_x86_keeps_default(config_root_real, monkeypatch):
    """非 x86_64 平台继续使用默认 Ascend 910B 目录。"""
    monkeypatch.setattr(locator.platform, "machine", lambda: "aarch64")
    assert (
        resolve_family_dir(config_root_real, "vllm-ascend", "Ascend910B_64G", "v0.18.0", True)
        == "ascend-a2"
    )


def test_resolve_family_dir_alias_bad_target_warns_and_fail(config_root_real, monkeypatch, caplog):
    """别名目标目录不存在(_ALIAS 配错)→ 记 WARNING 并 fail-fast,不静默兜底。"""
    monkeypatch.setitem(locator._ALIAS, "mycard", "nonexistent-dir")
    with caplog.at_level(logging.WARNING):
        with pytest.raises(FileNotFoundError, match="No configuration assets"):
            resolve_family_dir(config_root_real, "vllm", "mycard", "", False)
    assert "alias" in caplog.text and "nonexistent-dir" in caplog.text
