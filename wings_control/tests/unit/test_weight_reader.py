"""weight/reader 单测(显存闸 weight_bytes / 收缩守卫 heads 的读取,docs/53 §7)。

用临时目录造假 index.json / config.json / *.safetensors,不碰真权重。
"""

from __future__ import annotations

import json

import pytest

from wings_ctl.weight.reader import read_num_attention_heads, resolve_weight_bytes


def test_weight_bytes_from_index(tmp_path):
    """首选:读 index.json 的 metadata.total_size。"""
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps({"metadata": {"total_size": 123456}}), encoding="utf-8"
    )
    assert resolve_weight_bytes(str(tmp_path)) == 123456


def test_weight_bytes_fallback_sum_shards(tmp_path):
    """兜底:无 index.json → 累加 *.safetensors 字节。"""
    (tmp_path / "a.safetensors").write_bytes(b"x" * 100)
    (tmp_path / "b.safetensors").write_bytes(b"y" * 50)
    assert resolve_weight_bytes(str(tmp_path)) == 150


def test_weight_bytes_index_bad_falls_back(tmp_path):
    """index.json 损坏 → 回退遍历 *.safetensors。"""
    (tmp_path / "model.safetensors.index.json").write_text("{bad json", encoding="utf-8")
    (tmp_path / "a.safetensors").write_bytes(b"z" * 200)
    assert resolve_weight_bytes(str(tmp_path)) == 200


def test_weight_bytes_raises_no_source(tmp_path):
    """既无 index 又无 shards → raise(显存闸缺输入)。"""
    with pytest.raises(ValueError, match="无法判定权重体积"):
        resolve_weight_bytes(str(tmp_path))


def test_weight_bytes_raises_not_dir():
    """model-path 非目录 → raise。"""
    with pytest.raises(ValueError, match="不是可读目录"):
        resolve_weight_bytes("/nonexistent/path/xyz")


def test_heads_read(tmp_path):
    """读到 num_attention_heads。"""
    (tmp_path / "config.json").write_text(
        json.dumps({"num_attention_heads": 64}), encoding="utf-8"
    )
    assert read_num_attention_heads(str(tmp_path)) == 64


def test_heads_missing_config_returns_none(tmp_path):
    """无 config.json → None(调用方 warn-skip)。"""
    assert read_num_attention_heads(str(tmp_path)) is None


def test_heads_missing_field_returns_none(tmp_path):
    """config.json 无该字段 → None。"""
    (tmp_path / "config.json").write_text(json.dumps({"hidden_size": 4096}), encoding="utf-8")
    assert read_num_attention_heads(str(tmp_path)) is None
