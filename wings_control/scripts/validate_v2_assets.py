#!/usr/bin/env python3
"""validate_v2_assets — v2 资产合法性离线校验（registry.md §5）。

检查 config/v2/ 下所有合一资产的 profile 块合法性：
- 必填四要素缺失
- 未注册 key
- 必填 key 值非法
- 可选 key 多值/多算子叠加
- `hardware` 值 ∉ 合法硬件表（config/v2/hardware_table.yaml）

用法：python scripts/validate_v2_assets.py [config_root]
退出码：0 = 全部合法；1 = 存在 error 级问题。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 允许从任意目录运行：把 src 加入 sys.path。
HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
sys.path.append(str(SRC))

from wings_ctl.loaders.profile_validator import validate_assets  # noqa: E402
from wings_ctl.loaders.v2_loader import load_v2_assets, v2_root  # noqa: E402
from wings_ctl.loaders.yaml_loader import load_yaml  # noqa: E402


def _load_legal_hardware(config_root: Path) -> set[str] | None:
    """读取合法硬件表（config/v2/hardware_table.yaml）；缺失 → None（不校验 hardware 合法性）。"""
    table = v2_root(config_root) / "hardware_table.yaml"
    if not table.is_file():
        return None
    data = load_yaml(table)
    hw = data.get("hardware") if isinstance(data, dict) else None
    if not isinstance(hw, list):
        return None
    return {str(h) for h in hw}


def main(argv: list[str]) -> int:
    config_root = Path(argv[0]) if argv else HERE.parent / "config"
    root = v2_root(config_root)
    if not root.is_dir():
        print(f"validate_v2_assets: no v2 asset tree at {root}; skip")
        return 0

    assets = load_v2_assets(config_root)
    legal = _load_legal_hardware(config_root)
    result = validate_assets(
        [{"path": str(a.path), "profile": a.profile} for a in assets],
        legal_hardware=legal,
    )

    if not result.issues:
        print(f"validate_v2_assets: OK ({len(assets)} assets valid)")
        return 0

    for issue in result.issues:
        level = "ERROR" if issue.severity == "error" else "WARN"
        print(f"  [{level}] {issue.path}: {issue.message}")
    if result.valid:
        print(f"validate_v2_assets: {len(assets)} assets, warnings only")
        return 0
    print(f"validate_v2_assets: FAILED ({len(result.errors())} error(s) in {len(assets)} assets)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
