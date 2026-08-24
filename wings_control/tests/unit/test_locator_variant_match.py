"""`load_model_config` 两步匹配单测(docs/48):精确 `variant_name` 优先 + `name_pattern` 家族兜底。

用临时 mock 资产(不依赖真实 config),覆盖:精确命中、精确冲突报错、name_pattern 兜底(向后兼容)、
多变体只传家族名报错、精确层优先于家族层。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wings_ctl.loaders.locator import load_model_config


def _write(models_dir: Path, model_dir: str, filename: str, *, name: str,
           name_pattern: str, variant_name: str | None = None) -> None:
    """在 mock models 目录下写一个最小 model.yaml。

    Args:
        models_dir: `.../models` 目录。
        model_dir: 模型目录名(如 "DeepSeek")。
        filename: yaml 文件名(变体文件,如 "d-fp8.yaml")。
        name: model.name。
        name_pattern: model.match[].name_pattern。
        variant_name: 可选 model.variant_name(缺省=不写,模拟存量未铺 variant_name)。
    """
    d = models_dir / model_dir
    d.mkdir(parents=True, exist_ok=True)
    parts = ["model:", f"  name: {name}"]
    if variant_name is not None:
        parts.append(f'  variant_name: "{variant_name}"')
    parts += ["  match:", f'    - name_pattern: "{name_pattern}"']
    (d / filename).write_text("\n".join(parts) + "\n", encoding="utf-8")


def _models_dir(tmp_path: Path) -> Path:
    """无版本层布局:engines/vllm/hw0/models。"""
    return tmp_path / "engines" / "vllm" / "hw0" / "models"


def _load(tmp_path: Path, model_name: str):
    """调 load_model_config(无版本层),返回 (data, path, matched)。"""
    return load_model_config(tmp_path, "hw0", "vllm", "", model_name, has_version_dir=False)


def test_exact_variant_name_wins(tmp_path):
    """精确 variant_name 命中 → 选对应文件(name_pattern 家族级会命中多个,但精确层先定)。"""
    md = _models_dir(tmp_path)
    _write(md, "DeepSeek", "d-fp8.yaml", name="DeepSeek", name_pattern="(?i)deepseek", variant_name="DeepSeek-fp8")
    _write(md, "DeepSeek", "d-nvfp4.yaml", name="DeepSeek", name_pattern="(?i)deepseek", variant_name="DeepSeek-nvfp4")
    _, path, matched = _load(tmp_path, "DeepSeek-nvfp4")
    assert path.name == "d-nvfp4.yaml"
    assert "variant_name=DeepSeek-nvfp4" in matched


def test_exact_variant_name_case_insensitive(tmp_path):
    """精确匹配大小写归一:MaaS 传 `DEEPSEEK-NVFP4` 命中 config `DeepSeek-nvfp4`。"""
    md = _models_dir(tmp_path)
    _write(md, "DeepSeek", "d-nvfp4.yaml", name="DeepSeek", name_pattern="(?i)deepseek", variant_name="DeepSeek-nvfp4")
    _, path, _ = _load(tmp_path, "DEEPSEEK-NVFP4")
    assert path.name == "d-nvfp4.yaml"


def test_exact_variant_name_conflict_raises(tmp_path):
    """两个文件声明相同 variant_name → ValueError(config 冲突,提示唯一化)。"""
    md = _models_dir(tmp_path)
    _write(md, "M", "a.yaml", name="M", name_pattern="(?i)m", variant_name="M-x")
    _write(md, "M", "b.yaml", name="M", name_pattern="(?i)m", variant_name="M-x")
    with pytest.raises(ValueError, match="variant_name conflict"):
        _load(tmp_path, "M-x")


def test_name_pattern_fallback_single(tmp_path):
    """无 variant_name(存量)+ name_pattern 唯一命中 → 兜底选中(向后兼容,行为不变)。"""
    md = _models_dir(tmp_path)
    _write(md, "Solo", "solo.yaml", name="Solo", name_pattern="(?i)solo")
    _, path, matched = _load(tmp_path, "Solo")
    assert path.name == "solo.yaml"
    assert matched == "(?i)solo"


def test_multi_variant_family_name_ambiguous_raises(tmp_path):
    """多变体 + 只传家族名(精确 0 命中)→ name_pattern 多命中 → 报错要完整变体名。"""
    md = _models_dir(tmp_path)
    _write(md, "DeepSeek", "d-fp8.yaml", name="DeepSeek", name_pattern="(?i)deepseek", variant_name="DeepSeek-fp8")
    _write(md, "DeepSeek", "d-nvfp4.yaml", name="DeepSeek", name_pattern="(?i)deepseek", variant_name="DeepSeek-nvfp4")
    with pytest.raises(ValueError, match="complete variant name"):
        _load(tmp_path, "DeepSeek")


def test_exact_precedence_over_pattern(tmp_path):
    """精确层优先:即使 name_pattern 会命中多个,精确 variant_name 命中即定(不报歧义)。"""
    md = _models_dir(tmp_path)
    _write(md, "DeepSeek", "d-fp8.yaml", name="DeepSeek", name_pattern="(?i)deepseek", variant_name="DeepSeek-fp8")
    _write(md, "DeepSeek", "d-nvfp4.yaml", name="DeepSeek", name_pattern="(?i)deepseek", variant_name="DeepSeek-nvfp4")
    _, path, _ = _load(tmp_path, "DeepSeek-fp8")
    assert path.name == "d-fp8.yaml"


def test_exact_variant_only_rejects_pattern_fallback(tmp_path):
    """验证 PD exact 模式拒绝唯一 name_pattern 命中，不降级到家族 recipe。"""
    md = _models_dir(tmp_path)
    _write(md, "Solo", "solo.yaml", name="Solo", name_pattern="(?i)solo")

    with pytest.raises(FileNotFoundError, match="exact model variant"):
        load_model_config(
            tmp_path,
            "hw0",
            "vllm",
            "",
            "Solo",
            has_version_dir=False,
            exact_variant_only=True,
        )
