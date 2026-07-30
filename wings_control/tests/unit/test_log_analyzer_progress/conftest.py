"""pytest fixtures and helpers for log_analyzer progress tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# ── 路径常量 ──────────────────────────────────────────────
# 本文件: wings_control/tests/unit/test_log_analyzer_progress/conftest.py
# PROJECT_ROOT → wings_control/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# ── sys.path 注入 ─────────────────────────────────────────
# PatternPluginManager._load_plugin() 使用 `from log_analyzer.plugins import ...`
# （引擎容器中的顶层包名），测试环境需将 src/wings_ctl 加入 sys.path，
# 使 log_analyzer 可作为顶层包导入。
SRC_WINGS_CTL = PROJECT_ROOT / "src" / "wings_ctl"
if str(SRC_WINGS_CTL) not in sys.path:
    sys.path.insert(0, str(SRC_WINGS_CTL))
DATA_DIR = Path(__file__).parent / "data"

# 构建层文件
DOCKERFILE_PATH = PROJECT_ROOT.parent / "build" / "wings-control" / "Dockerfile"
WINGS_START_PATH = PROJECT_ROOT / "wings_start.sh"


# ── Fixtures ─────────────────────────────────────────────
@pytest.fixture
def data_dir() -> Path:
    """日志 demo 文件目录。"""
    return DATA_DIR


@pytest.fixture
def dockerfile_path() -> Path:
    return DOCKERFILE_PATH


@pytest.fixture
def wings_start_path() -> Path:
    return WINGS_START_PATH


# ── 辅助函数 ─────────────────────────────────────────────
def make_config(engine: str, hardware: str = "nvidia", mode: str = "single") -> dict[str, Any]:
    """构造 LogAnalyzer 配置字典。

    Args:
        engine: 引擎名称 (vllm / vllm-ascend / sglang / mindie)
        hardware: 硬件类型 (nvidia / ascend)
        mode: 部署模式 (single / distributed)
    """
    return {
        "engine": engine,
        "deployment_mode": mode,
        "hardware": hardware,
        "backend_port": "17000",
    }


def run_progress_analysis(
    log_path: Path,
    config: dict[str, Any],
    tmp_path: Path,
) -> tuple[Any, list[dict[str, Any]]]:
    """将日志文件逐行喂入 LogAnalyzer，返回 (analyzer, captured_entries)。

    捕获所有 write_progress 调用，每条记录为 kwargs 字典。

    Args:
        log_path: 日志文件路径
        config: LogAnalyzer 配置字典
        tmp_path: 临时目录（用于 progress.jsonl）

    Returns:
        (analyzer实例, write_progress调用列表)
    """
    from wings_ctl.log_analyzer.log_analyzer import LogAnalyzer

    progress_file = str(tmp_path / "progress.jsonl")
    analyzer = LogAnalyzer(config, str(log_path), progress_file)

    # 捕获所有 write_progress 调用
    captured: list[dict[str, Any]] = []
    original_write = analyzer.stage_progress.write_progress

    def capture(**kwargs: Any) -> None:
        captured.append(dict(kwargs))
        original_write(**kwargs)

    analyzer.stage_progress.write_progress = capture  # type: ignore[method-assign]

    # 逐行喂入（模拟 tail -F 实时读取）
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            analyzer._parse_log_line(line)

    return analyzer, captured


def extract_phase_codes(captured: list[dict[str, Any]]) -> list[str]:
    """从捕获的 write_progress 调用中提取 phase_code 序列（去重保序）。"""
    seen: set[str] = set()
    result: list[str] = []
    for entry in captured:
        code = entry.get("phase_code", "")
        if code not in seen:
            seen.add(code)
            result.append(code)
    return result


def get_final_progress(captured: list[dict[str, Any]]) -> int:
    """获取最后一次 write_progress 调用的 progress 值。"""
    if not captured:
        return 0
    return int(captured[-1].get("progress", 0))


def has_status(captured: list[dict[str, Any]], status: str) -> bool:
    """检查是否有任何 write_progress 调用使用了指定 status。"""
    return any(e.get("status") == status for e in captured)


def get_phase_progress_map(
    captured: list[dict[str, Any]],
) -> dict[str, list[int]]:
    """提取每个 phase_code 对应的所有 progress 值（按出现顺序）。

    Returns:
        {phase_code: [progress1, progress2, ...]}
    """
    result: dict[str, list[int]] = {}
    for entry in captured:
        code = entry.get("phase_code", "")
        progress = int(entry.get("progress", 0))
        result.setdefault(code, []).append(progress)
    return result


def get_first_progress_for_phase(captured: list[dict[str, Any]], phase_code: str) -> int | None:
    """获取指定 phase_code 第一次出现的 progress 值。"""
    for entry in captured:
        if entry.get("phase_code") == phase_code:
            return int(entry.get("progress", 0))
    return None


def get_max_progress_for_phase(captured: list[dict[str, Any]], phase_code: str) -> int | None:
    """获取指定 phase_code 的最大 progress 值。"""
    progress_map = get_phase_progress_map(captured)
    values = progress_map.get(phase_code, [])
    return max(values) if values else None
