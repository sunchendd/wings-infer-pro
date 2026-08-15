"""EngineResolver — 解析引擎版本并处理 latest 回退。

输入: config_root (Path), hardware_family (str), engine (str), ENGINE_VERSION env var
输出: EngineVersion

精确版本目录未命中时按 latest 回退 + WARNING + audit 记录。
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional, Tuple

from wings_ctl.core.models import EngineVersion

logger = logging.getLogger(__name__)

# 匹配磁盘上的配置目录名，例如 v0.19.0、v0.21.0rc、v0.17.1。
# 示例：v0.21.0rc 可匹配；v0.21.0rc1-20260709144216 不可直接匹配。
_VERSION_DIR_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:[A-Za-z]+\d*)?$")
# 匹配运行时传入的版本，并提取基础版本和预发布渠道。
# 示例：v0.21.0rc1-20260709144216 → v0.21.0 + rc，最终查找 v0.21.0rc 目录。
_REQUESTED_VERSION_RE = re.compile(r"^v?(\d+\.\d+\.\d+)([A-Za-z]+)(?:\d+)?(?:[-+].*)?$")


def _parse_version_tuple(ver_str: str) -> Optional[Tuple[int, int, int]]:
    """尝试将版本字符串解析为 (major, minor, patch)。"""
    cleaned = ver_str.strip().lstrip("vV")
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", cleaned)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m2 = re.match(r"(\d+)\.(\d+)", cleaned)
    if m2:
        return (int(m2.group(1)), int(m2.group(2)), 0)
    return None


def _find_latest_version_dir(engine_dir: Path) -> Optional[str]:
    """在 engine 目录下找最高版本号的子目录。"""
    versions = []
    if not engine_dir.is_dir():
        return None
    for child in engine_dir.iterdir():
        if child.is_dir() and _VERSION_DIR_RE.match(child.name):
            tup = _parse_version_tuple(child.name)
            if tup:
                versions.append((tup, child.name))
    if not versions:
        return None
    versions.sort(reverse=True)
    return versions[0][1]


def resolve_engine_version(
    config_root: Path,
    hardware_family: str,
    engine: str = "vllm",
    *,
    require_exact: bool = False,
) -> EngineVersion:
    """解析引擎版本,必要时执行 latest 回退。

    Args:
        config_root: 配置根目录(含 engines/ 子目录)。
        hardware_family: 硬件族标识(当前函数不参与路径计算,保留为接口兼容参数)。
        engine: 引擎名称(如 "vllm")。
        require_exact: 是否要求显式 ``ENGINE_VERSION`` 且禁止 latest 回退；PD 使用。

    Returns:
        EngineVersion 实例。

    Raises:
        ValueError: ``require_exact=True`` 但未设置 ``ENGINE_VERSION``。
        FileNotFoundError: 严格版本未命中，或无法找到任何有效版本目录。
    """
    requested_raw = os.environ.get("ENGINE_VERSION", "").strip() or None
    if require_exact and requested_raw is None:
        raise ValueError("PD 场景必须显式设置 ENGINE_VERSION，且版本必须命中 exact recipe。")
    engine_root = config_root / "engines" / engine

    # 版本层有无,靠"目录名像不像版本号"这条通用规则判定,不靠引擎名。
    # 拼到 engines/{engine}/ 后,看下一层子目录名是否匹配 vX.Y.Z:
    #   有匹配(如 vllm-ascend 的 v0.18.0)→ 有版本层,走版本目录解析 + latest 回退;
    #   全不匹配(如 vllm 下全是 h100/h200 硬件名)→ 无版本层,resolved 置空、ENGINE_VERSION 不参与路径。
    # 这样新增引擎(sglang 等)无需改代码、无需声明:目录建得像版本号就有版本层,反之没有。
    has_version_dir = (
        any(child.is_dir() and _VERSION_DIR_RE.match(child.name) for child in engine_root.iterdir())
        if engine_root.is_dir()
        else False
    )

    if not has_version_dir:
        return EngineVersion(
            requested=requested_raw,
            resolved="",
            is_fallback=False,
            has_version_dir=False,
        )

    engine_dir = engine_root

    if requested_raw:
        # 先按原样查找目录，例如传入 0.18.0 时查找 v0.18.0。
        # 这里统一补上 v 前缀，但保留用户传入的原始版本到 requested 字段。
        version_dir_name = requested_raw if requested_raw.startswith("v") else f"v{requested_raw}"
        exact_path = engine_dir / version_dir_name

        # 有些运行时版本会比配置目录更详细，例如：
        # v0.21.0rc1-20260709144216 → v0.21.0rc。
        # 从完整版本中提取基础版本和渠道名称，生成配置目录名。
        normalized_match = _REQUESTED_VERSION_RE.match(requested_raw)
        normalized_dir_name = f"v{normalized_match.group(1)}{normalized_match.group(2)}" if normalized_match else None

        # 按“原始目录名 → 简化后的目录名”的顺序查找，优先保证精确匹配。
        candidate_names = [version_dir_name]
        if normalized_dir_name and normalized_dir_name != version_dir_name:
            candidate_names.append(normalized_dir_name)

        for candidate_name in candidate_names:
            if (engine_dir / candidate_name).is_dir():
                logger.info("EngineResolver: matched requested version %s to %s", requested_raw, candidate_name)
                return EngineVersion(
                    requested=requested_raw,
                    resolved=candidate_name.lstrip("v"),
                    is_fallback=False,
                    has_version_dir=True,
                )
        if require_exact:
            attempted = ", ".join(candidate_names)
            raise FileNotFoundError(
                f"PD ENGINE_VERSION={requested_raw!r} 未命中 exact 配置目录；engine={engine!r}，已尝试={attempted}。"
            )
        logger.warning(
            "EngineResolver: requested version '%s' not found at %s; falling back to latest available version.",
            requested_raw,
            exact_path,
        )

    latest = _find_latest_version_dir(engine_dir)
    if latest is None:
        raise FileNotFoundError(
            f"No version directories found under {engine_dir}. Cannot resolve engine version for {engine}."
        )

    resolved_version = latest.lstrip("v")
    # is_fallback 仅表示"用户显式请求了某版本,但未命中而回退到 latest"。
    # 未设 ENGINE_VERSION(requested=None)时使用 latest 属于默认行为,不算 fallback。
    is_fallback = requested_raw is not None
    if is_fallback:
        logger.warning(
            "EngineResolver: FALLBACK requested=%s resolved=%s",
            requested_raw,
            resolved_version,
        )
    else:
        logger.info("EngineResolver: no ENGINE_VERSION set, using latest=%s", resolved_version)

    return EngineVersion(
        requested=requested_raw,
        resolved=resolved_version,
        is_fallback=is_fallback,
        has_version_dir=True,
    )
