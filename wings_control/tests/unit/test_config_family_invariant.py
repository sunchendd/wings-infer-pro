"""config 硬件目录不变量:同一 engine[/version] 下,同型号不许"裸目录"与"带 _<N>G 后缀目录"并存。

为什么守这条:locator.resolve_family_dir 用"剥后缀兜底"把普通卡的冗余显存后缀去掉后命中裸目录
(如 H100_80G → h100)。若某型号同时存在裸目录和后缀目录(如 h20 与 h20_96G 并存),一个不存在的
显存档(h20_80G)会被剥后缀静默坍缩到裸 h20,用错 recipe。这条断言防 config 未来违反该前提。
"""

from __future__ import annotations

from pathlib import Path

from wings_ctl.hardware.resolver import strip_gpu_mem_suffix


def _family_parents(engines_dir: Path) -> set[Path]:
    """收集所有"直接含 hardware_family 目录(其下有 models/)"的父目录。

    Args:
        engines_dir: config/engines 目录。

    Returns:
        父目录集合(= engines/{engine} 或 engines/{engine}/v{version})。
    """
    parents: set[Path] = set()
    for models_dir in engines_dir.rglob("models"):
        if models_dir.is_dir():
            parents.add(models_dir.parent.parent)  # {parent}/{family}/models → {parent}
    return parents


def test_config_family_dir_no_bare_and_suffixed_collision(config_root_real):
    """真实 config:任一 engine[/version] 下,带 _<N>G 后缀目录的裸型号名不得也是一个裸目录。"""
    violations: list[str] = []
    for parent in sorted(_family_parents(config_root_real / "engines")):
        families = [c.name for c in parent.iterdir() if (c / "models").is_dir()]
        bare = {f.casefold() for f in families if strip_gpu_mem_suffix(f) == f}
        for f in families:
            if strip_gpu_mem_suffix(f) != f:  # 该目录带显存后缀
                base = strip_gpu_mem_suffix(f).casefold()
                if base in bare:
                    violations.append(f"{parent.name}: '{f}' 与裸目录 '{base}' 并存")
    assert not violations, (
        "config 硬件目录不变量被破坏(同型号裸目录 + 后缀目录并存 → 剥后缀会静默坍缩):\n"
        + "\n".join(violations)
    )
