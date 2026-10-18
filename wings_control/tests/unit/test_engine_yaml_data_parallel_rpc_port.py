"""全仓 YAML 的 data_parallel_rpc_port 类型回归测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.asset_yaml_cache import load_asset_yaml


REPOSITORY_ROOT = Path(__file__).parents[3]


def _find_non_integer_ports(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key == "data_parallel_rpc_port" and (
                isinstance(child, bool) or not isinstance(child, int)
            ):
                errors.append(f"{child_path}={child!r}")
            errors.extend(_find_non_integer_ports(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_find_non_integer_ports(child, f"{path}[{index}]"))
    return errors


def test_all_repository_yamls_use_integer_data_parallel_rpc_port() -> None:
    errors: list[str] = []

    def _contains_data_parallel_rpc_port(path: Path) -> bool:
        return "data_parallel_rpc_port" in path.read_text(encoding="utf-8")

    def _is_candidate_yaml(path: Path) -> bool:
        return ".git" not in path.parts and _contains_data_parallel_rpc_port(path)

    yaml_paths = sorted(path for path in REPOSITORY_ROOT.rglob("*.yaml") if _is_candidate_yaml(path))
    yaml_paths += sorted(path for path in REPOSITORY_ROOT.rglob("*.yml") if _is_candidate_yaml(path))
    yaml_paths.sort()

    for yaml_path in yaml_paths:
        document = load_asset_yaml(yaml_path)
        errors.extend(
            f"{yaml_path.relative_to(REPOSITORY_ROOT)}:{error}"
            for error in _find_non_integer_ports(document, "")
        )

    assert not errors, "data_parallel_rpc_port must be a YAML integer:\n" + "\n".join(errors)
