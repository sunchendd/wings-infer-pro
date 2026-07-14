"""version_resolver.is_fallback 语义单测(F8 修复)。

锁定:is_fallback 仅指"显式请求了某版本但未精确命中、回退到 latest";
未设 ENGINE_VERSION 走 latest 是缺省选择,**不算 fallback**(旧代码恒 True 是 bug)。
"""

from __future__ import annotations

from wings_ctl.engines.version_resolver import (
    _find_latest_version_dir,
    _parse_version_tuple,
    resolve_engine_version,
)


# ─── _parse_version_tuple(版本字符串解析,含两段式/非法)──────────────────────

def test_parse_version_three_part():
    """三段式 vX.Y.Z → (X,Y,Z)。"""
    assert _parse_version_tuple("v0.18.0") == (0, 18, 0)


def test_parse_version_two_part():
    """两段式 X.Y → (X,Y,0)(缺省 patch)。"""
    assert _parse_version_tuple("0.18") == (0, 18, 0)


def test_parse_version_invalid_returns_none():
    """非法格式 → None(不抛)。"""
    assert _parse_version_tuple("garbage") is None


# ─── _find_latest_version_dir(扫版本目录取最高)──────────────────────────────

def test_find_latest_skips_non_version_children(tmp_path):
    """混入非版本子目录/文件 → 跳过,只在 vX.Y.Z 里取最高。"""
    (tmp_path / "v0.1.0").mkdir()
    (tmp_path / "v0.2.0").mkdir()
    (tmp_path / "not-a-version").mkdir()   # 跳过(正则不匹配)
    (tmp_path / "afile.txt").write_text("x")  # 跳过(非目录)
    assert _find_latest_version_dir(tmp_path) == "v0.2.0"


def test_find_latest_empty_dir_returns_none(tmp_path):
    """目录无任何版本子目录 → None。"""
    (tmp_path / "readme.md").write_text("x")
    assert _find_latest_version_dir(tmp_path) is None


def test_find_latest_nonexistent_dir_returns_none(tmp_path):
    """目录不存在 → None。"""
    assert _find_latest_version_dir(tmp_path / "nope") is None


def _make_engine_dirs(tmp_path, engine, versions):
    """在 tmp 下建 engines/{engine}/vX.Y.Z 目录,返回 config_root。"""
    base = tmp_path / "engines" / engine
    for v in versions:
        (base / v).mkdir(parents=True)
    return tmp_path


def test_no_engine_version_uses_latest_not_fallback(tmp_path, monkeypatch):
    """未设 ENGINE_VERSION → 取 latest,但 is_fallback=False(缺省选择,非回退)。"""
    monkeypatch.delenv("ENGINE_VERSION", raising=False)
    root = _make_engine_dirs(tmp_path, "vllm-ascend", ["v0.17.0", "v0.18.0"])
    ev = resolve_engine_version(root, "ascend-a3", engine="vllm-ascend")
    assert ev.resolved == "0.18.0"
    assert ev.is_fallback is False     # 关键:未请求 → 不算 fallback
    assert ev.requested is None


def test_exact_match_not_fallback(tmp_path, monkeypatch):
    """精确命中请求版本 → is_fallback=False。"""
    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    root = _make_engine_dirs(tmp_path, "vllm-ascend", ["v0.17.0", "v0.18.0"])
    ev = resolve_engine_version(root, "ascend-a3", engine="vllm-ascend")
    assert ev.resolved == "0.18.0"
    assert ev.is_fallback is False


def test_requested_not_found_is_fallback(tmp_path, monkeypatch):
    """请求的版本不存在 → 回退 latest 且 is_fallback=True(§2.7 requested≠resolved)。"""
    monkeypatch.setenv("ENGINE_VERSION", "9.9.9")
    root = _make_engine_dirs(tmp_path, "vllm-ascend", ["v0.17.0", "v0.18.0"])
    ev = resolve_engine_version(root, "ascend-a3", engine="vllm-ascend")
    assert ev.resolved == "0.18.0"
    assert ev.is_fallback is True
    assert ev.requested == "9.9.9"
