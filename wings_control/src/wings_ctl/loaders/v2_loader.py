"""v2_loader — v2 资产扫描、合一文件解析与 profile 匹配。

对应设计 `docs/design/wings-yaml-v2.md` §3/§6。

v2 资产体系：
- 单文件合一：一个 yaml 同时含基线（`scenarios` 等 V1 基线块）与加速（`smart_accel` 块），
  顶部加 `profile` 块用于索引。
- 目录仅作物理组织，不参与匹配。匹配完全由 profile 承担，扫描器递归遍历 v2 资产树。
- 组织形式约定为 `v2/{engine}/{version}/{hardware}/{model}/{variant}.yaml`，仅为约定。

本模块为纯 IO + 匹配层，不依赖 fcntl，可独立 dry-run 验证。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from wings_ctl.loaders.profile_registry import ProfileAmbiguityError, _norm_str, evaluate_profile, resolve
from wings_ctl.loaders.yaml_loader import load_yaml

logger = logging.getLogger(__name__)

# v2 资产根目录名（config_root 下的子目录）。
V2_ROOT_NAME = "v2"

# 合法硬件表（含别名块）：与 v2 资产树同目录维护，但不是资产（无 profile 块），扫描时跳过。
HARDWARE_TABLE_NAME = "hardware_table.yaml"

# 合一文件顶层块。
SCHEMA_KEY = "schema"
PROFILE_KEY = "profile"
MODEL_KEY = "model"
ENGINE_CONFIG_KEY = "engine_config"
SMART_ACCEL_KEY = "smart_accel"


@dataclass
class V2Asset:
    """一个已解析的 v2 合一资产。

    Attributes:
        path: 资产文件路径。
        profile: profile 索引块（扁平 key-value）。
        data: 完整合一文件 dict。
        model: model 元信息块（V1 基线原样）。
        scenarios: scenarios 块（V1 基线原样，含各 topology 策略）。
        smart_accel: smart_accel 块（V1 加速原样，可选）。
        features: features 块（V1 基线原样，可选）。
    """

    path: Path
    profile: Dict[str, Any]
    data: Dict[str, Any]
    model: Dict[str, Any] = field(default_factory=dict)
    scenarios: Dict[str, Any] = field(default_factory=dict)
    smart_accel: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, Any] = field(default_factory=dict)


def v2_root(config_root: Path) -> Path:
    """返回 v2 资产根目录。"""
    return Path(config_root) / V2_ROOT_NAME


def scan_v2_assets(config_root: Path) -> List[Path]:
    """递归遍历 v2 资产树，收集所有 `.yaml` 文件。

    目录仅作物理组织，不参与匹配；扫描器递归遍历。

    Args:
        config_root: 配置根目录（含 v2/ 子目录）。

    Returns:
        排序后的 v2 yaml 文件路径列表；v2 目录不存在 → 空列表。
    """
    root = v2_root(config_root)
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.rglob("*.yaml")
        if p.is_file() and p.name != HARDWARE_TABLE_NAME
    )


def parse_v2_asset(path: Path) -> Optional[V2Asset]:
    """解析单个 v2 合一文件。

    Args:
        path: v2 yaml 文件路径。

    Returns:
        :class:`V2Asset`；文件缺失/非 dict/缺 profile 块 → None（跳过 + 记录）。
    """
    if not path.is_file():
        return None
    try:
        data = load_yaml(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("v2_loader: YAML parse failed %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("v2_loader: %s is not a dict; skip", path)
        return None
    profile = data.get(PROFILE_KEY)
    if not isinstance(profile, dict):
        logger.warning("v2_loader: %s missing profile block; skip", path)
        return None
    model = data.get(MODEL_KEY)
    scenarios = data.get("scenarios")
    smart_accel = data.get(SMART_ACCEL_KEY)
    features = data.get("features")
    return V2Asset(
        path=path,
        profile=profile,
        data=data,
        model=model if isinstance(model, dict) else {},
        scenarios=scenarios if isinstance(scenarios, dict) else {},
        smart_accel=smart_accel if isinstance(smart_accel, dict) else {},
        features=features if isinstance(features, dict) else {},
    )


def load_v2_assets(config_root: Path) -> List[V2Asset]:
    """扫描并解析 v2 资产树，返回全部有效资产。

    Args:
        config_root: 配置根目录。

    Returns:
        有效资产列表（缺 profile 块/解析失败的跳过）。
    """
    assets: List[V2Asset] = []
    for path in scan_v2_assets(config_root):
        asset = parse_v2_asset(path)
        if asset is not None:
            assets.append(asset)
    return assets


def load_hardware_aliases(config_root: Path) -> Dict[str, str]:
    """读取硬件别名表（config/v2/hardware_table.yaml 的 `aliases` 块）。

    别名表把调用方下发的别名硬件归一化到合法硬件（如 `ascend910` → `Ascend910C_64G`）。
    匹配时，ctx 的 hardware 若命中别名，先归一化到目标硬件再匹配资产 profile.hardware。

    Args:
        config_root: 配置根目录。

    Returns:
        ``{归一化别名: 目标硬件}`` 映射；别名表缺失/为空 → 空 dict。
    """
    table = v2_root(config_root) / HARDWARE_TABLE_NAME
    if not table.is_file():
        return {}
    data = load_yaml(table)
    aliases = data.get("aliases") if isinstance(data, dict) else None
    if not isinstance(aliases, dict):
        return {}
    return {_norm_str(k): str(v) for k, v in aliases.items()}


def _normalize_ctx_hardware(ctx: Dict[str, Any], aliases: Dict[str, str]) -> Dict[str, Any]:
    """把 ctx 的 hardware 通过别名表归一化（命中别名 → 替换为目标硬件）。

    Args:
        ctx: 查找上下文。
        aliases: ``{归一化别名: 目标硬件}`` 映射。

    Returns:
        归一化后的 ctx（未命中别名 → 原样返回）。
    """
    hw = ctx.get("hardware")
    if hw is None or not aliases:
        return ctx
    target = aliases.get(_norm_str(hw))
    if target is None:
        return ctx
    return {**ctx, "hardware": target}


def locate_v2(config_root: Path, ctx: Dict[str, Any]) -> Optional[V2Asset]:
    """按 profile 匹配 v2 资产，偏序裁决取最特化者。

    Args:
        config_root: 配置根目录。
        ctx: 查找上下文（engine/version/hardware/model + 可选 key）。

    Returns:
        命中的最特化资产；无命中 → None（上层回退 v1）。
        多个候选等价或互不偏序（歧义）→ 告警 + 确定性选第一个，不再 fail-fast。
    """
    # 别名归一化：ctx 的 hardware 若命中别名表，先归一化到目标硬件再匹配。
    aliases = load_hardware_aliases(config_root)
    ctx = _normalize_ctx_hardware(ctx, aliases)
    assets = load_v2_assets(config_root)
    matched = [a for a in assets if evaluate_profile(a.profile, ctx)]
    if not matched:
        return None
    try:
        winner_profile = resolve([a.profile for a in matched], ctx)
    except ProfileAmbiguityError as exc:
        # 歧义（等价重复 / 互不偏序）：告警 + 确定性选第一个，不再 fail-fast。
        # 由资产作者在离线校验阶段解决；运行时先跑起来。
        logger.warning("v2 asset ambiguity; picking the first matched asset: %s", exc)
        return matched[0]
    for asset in matched:
        if asset.profile == winner_profile:
            return asset
    # 理论上不会到达（resolve 返回的 profile 必在 matched 中）。
    return None
