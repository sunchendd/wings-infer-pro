"""本批 draft_arch 资产的场景必须是对应 engine recipe 的子集。"""

from pathlib import Path
from typing import Any

import pytest

from tests.asset_yaml_cache import load_asset_yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SMART_ROOT = REPO_ROOT / "src" / "wings_accel" / "smart-accel"
ENGINE_ROOT = REPO_ROOT / "config" / "engines"


def _load(path: Path) -> dict[str, Any]:
    return load_asset_yaml(path) or {}


def _draft_assets() -> list[Path]:
    """返回本批需守护的 ERNIE MTP 和 ARM+NPU 草稿资产。"""
    ernie = SMART_ROOT.glob("vllm/v0.23.0/*/models/ERNIE-4.5-21B-A3B-PT/*.yaml")
    ascend = (
        path
        for path in SMART_ROOT.glob("vllm-ascend/v0.21.0rc/ascend-a[23]/models/*/*.yaml")
        if "draft_arch" in path.read_text(encoding="utf-8")
    )
    return sorted([*ernie, *ascend])


def _engine_candidates(smart_path: Path, variant_name: str) -> list[Path]:
    parts = smart_path.relative_to(SMART_ROOT).parts
    engine, version, hardware = parts[:3]
    candidates = []
    for path in (ENGINE_ROOT / engine).glob("**/models/*/*.yaml"):
        if hardware not in path.parts:
            continue
        model = _load(path).get("model") or {}
        if str(model.get("variant_name", "")).casefold() == variant_name.casefold():
            candidates.append(path)
    versioned = [path for path in candidates if version in path.parts]
    return versioned or candidates


@pytest.mark.parametrize("smart_path", _draft_assets(), ids=lambda path: str(path.relative_to(SMART_ROOT)))
def test_draft_asset_scenarios_are_engine_subset(smart_path: Path):
    smart = _load(smart_path)
    variant_name = smart["model"]["variant_name"]
    candidates = _engine_candidates(smart_path, variant_name)
    assert len(candidates) == 1, f"{smart_path}: engine recipe candidates={candidates}"

    engine = _load(candidates[0])
    smart_scenarios = set((smart.get("smart_accel") or {}).keys())
    engine_scenarios = set((engine.get("scenarios") or {}).keys())
    assert smart_scenarios <= engine_scenarios, (
        f"{smart_path}: undeclared scenarios={sorted(smart_scenarios - engine_scenarios)}, "
        f"engine scenarios={sorted(engine_scenarios)}"
    )
