"""asset_yaml_cache: 缓存命中、隔离性(每次返回独立副本)、失效与解析一致性。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.asset_yaml_cache import load_asset_yaml


def test_load_asset_yaml_returns_independent_copies(tmp_path: Path):
    """每次读取返回独立副本:修改返回值不得影响后续读取(测试之间不共享状态)。"""
    path = tmp_path / "asset.yaml"
    path.write_text("model:\n  variant_name: demo\n  scenarios:\n    a: 1\n", encoding="utf-8")

    first = load_asset_yaml(path)
    first["model"]["variant_name"] = "mutated"
    first["model"]["scenarios"]["a"] = 999

    second = load_asset_yaml(path)

    assert second == {"model": {"variant_name": "demo", "scenarios": {"a": 1}}}
    assert second is not first


def test_load_asset_yaml_invalidates_after_rewrite(tmp_path: Path):
    """文件被改写(内容长度或时间戳变化)后必须返回新内容,不得命中旧缓存。"""
    path = tmp_path / "asset.yaml"
    path.write_text("a: 1\n", encoding="utf-8")
    assert load_asset_yaml(path) == {"a": 1}

    path.write_text("a: 200\n", encoding="utf-8")

    assert load_asset_yaml(path) == {"a": 200}


def test_load_asset_yaml_returns_none_for_empty_file(tmp_path: Path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    assert load_asset_yaml(path) is None


@pytest.mark.parametrize(
    "text",
    [
        "a: 1\n",
        "a: yes\nb: ~\n",
        "base: &b {x: 1}\nchild:\n  <<: *b\n  y: 2\n",
        "a: 010\nb: 1:30\nc: .inf\n",
        "a: 1\na: 2\n",
        'a: "123"\nb: |\n  x\n',
    ],
)
def test_load_asset_yaml_matches_safe_load(tmp_path: Path, text: str):
    """缓存使用的 C 解析器必须与生产 ``yaml.safe_load`` 给出相同数据。"""
    path = tmp_path / "asset.yaml"
    path.write_text(text, encoding="utf-8")

    assert load_asset_yaml(path) == yaml.safe_load(text)


@pytest.mark.parametrize(
    "payload",
    [
        '!!python/object/apply:subprocess.check_output [["echo pwned"]]',
        "!!python/object/new:tuple\n"
        "  - !!python/object/new:map\n"
        "    - !!python/name:eval\n"
        "    - [ \"__import__('os').system('echo pwned')\" ]",
        "!!python/name:os.system",
    ],
)
def test_load_asset_yaml_rejects_python_object_tags(tmp_path: Path, payload: str):
    """资产读取只走 safe 构造器:``!!python/*`` 危险标签必须报错,且异常不入缓存。"""
    path = tmp_path / "malicious.yaml"
    path.write_text(payload + "\n", encoding="utf-8")

    for _ in range(2):
        with pytest.raises(yaml.constructor.ConstructorError):
            load_asset_yaml(path)
