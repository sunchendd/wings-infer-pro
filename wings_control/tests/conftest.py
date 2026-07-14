"""pytest fixtures for wings_ctl tests."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent  # Wings-infer-refactor/
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def config_root() -> Path:
    """Legacy fixture — 有 _platform.yaml,专测双层合并路径。"""
    return FIXTURES_DIR / "config_legacy"


@pytest.fixture
def config_root_real() -> Path:
    """正式配置资产 — 真实工具产物格式(无 _platform.yaml)。"""
    return PROJECT_ROOT / "config"


@pytest.fixture
def hardware_info_path() -> Path:
    return FIXTURES_DIR / "hardware_info.json"
