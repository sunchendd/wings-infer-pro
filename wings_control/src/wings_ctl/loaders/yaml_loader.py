"""yaml_loader — 通用 YAML 读取工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def load_yaml(path: Path) -> Dict[str, Any]:
    """读取 YAML 文件并返回 dict。空文件返回空 dict。"""
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
