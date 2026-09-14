"""小策略层入口:在模板命中后做参数改写。

本模块的职责很单一:
1. 不改模板原始 dict;
2. 只返回覆盖层(override)和说明信息(notes);
3. 由外层统一合并并写入 trace。

当前只实现 ``device_count_transform``。其它小策略层能力在对应模块处理:
``FeatureOverlay``(模型级特性参数)与 ``TopologyRuntimeInject``(多机运行时注入)。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from wings_ctl.engines.extension import get_engine_extension
from wings_ctl.engines.delivery_contract import (
    build_parallelism_override,
    read_parallelism_values,
)
from wings_ctl.strategy.parallelism import resolve_replica_tp_dp

logger = logging.getLogger(__name__)

# (engine_config, ctx) -> (override_layer, notes_patch)
Transform = Callable[[dict, dict[str, Any]], tuple[dict, dict]]

# device_count_transform 写进 notes 的 strategy status —— "device_count_status" 取值全集
# (会出现在 audit / resolution_notes,排查 DP/TP 时对照):
#   - "noop_equals_template" : 按 device_count 算出的 DP == 模板 DP,不覆盖(仅记录)。
#   - "overridden"           : device_count 改了 DP(DP = cnt // TP),写覆盖层。
#   - "tp_shrunk"            : 单机 cnt < TP,收缩 TP=cnt、DP=1(已过 resolver 前置显存/heads 闸)。
# 未下发 device_count 时不写 status(返回空 override + 空 notes)。


def generic_fallback_parallelism(
    engine_config: dict,
    device_count: int | None,
    *,
    engine: str,
) -> tuple[dict, dict]:
    """为 generic/default standalone 保底选择单个 TP 组。

    generic 模板中的 TP 只是无卡数输入时的占位值，不能据此扩展 DP。下发卡数时
    使用全部设备组成一个 TP 组；DP 不显式渲染，沿用引擎默认值 1。返回值由 resolver
    作为独立 trace 层合并，用户 CLI 仍可在更高优先级覆盖。
    """
    if device_count is None:
        template_tp, template_dp, _ = read_parallelism_values(engine_config, engine=engine)
        logger.warning(
            "Generic hardware fallback has no device-count; keeping template parallelism in best-effort mode"
        )
        return {}, {
            "generic_fallback_parallelism_status": "template_no_device_count",
            "generic_fallback_resolved_tp": str(template_tp),
            "generic_fallback_resolved_dp": str(template_dp),
        }
    if device_count <= 0:
        raise ValueError(f"device-count={device_count} is invalid; it must be a positive integer")
    return build_parallelism_override(engine=engine, tp=device_count), {
        "generic_fallback_parallelism_status": "tp_from_device_count",
        "generic_fallback_device_count": str(device_count),
        "generic_fallback_resolved_tp": str(device_count),
        "generic_fallback_resolved_dp": "1",
    }


def device_count_transform(engine_config: dict, ctx: dict[str, Any]) -> tuple[dict, dict]:
    """根据 ``device_count`` 计算单机场景的生效 TP/DP。

    规则:
    - 只读模板 TP,不会在这里推导新 TP;
    - ``device_count`` 未提供时不改参数;
    - ``device_count >= TP`` 时仅计算 DP;
    - ``device_count < TP`` 时进入收缩分支(TP=cnt,DP=1)。

    本函数只返回覆盖层,不直接改 ``engine_config``。

    Args:
        engine_config: 模板中的 engine_config(只读)。
        ctx: 上下文,至少包含 ``device_count``。

    Returns:
        ``(override_layer, notes)``:
            - override_layer: 需要覆盖的键;空 dict 表示不改参数。
            - notes: 记录本次计算的关键输入与结果,用于审计与排查。

    Raises:
        ValueError: 参数组合非法(由 ``resolve_replica_tp_dp`` 抛出)。
    """
    device_count = ctx.get("device_count")
    if device_count is None:
        return {}, {}

    engine = ctx.get("engine", "vllm")
    tp, template_dp, _ = read_parallelism_values(engine_config, engine=engine)

    # 单机:cnt>=TP 算 DP;cnt<TP 收缩 TP。
    tp_eff, resolved_dp = resolve_replica_tp_dp(device_count, tp)
    notes = {
        "device_count_tp": str(tp),
        "device_count_template_dp": str(template_dp),
        "device_count_value": str(device_count),
        "device_count_resolved_dp": str(resolved_dp),
    }
    if tp_eff != tp:
        # 收缩:TP=cnt、DP=1(容量/heads 校验在 resolver 前置完成)
        notes["device_count_tp_eff"] = str(tp_eff)
        notes["device_count_status"] = "tp_shrunk"
        logger.info("device-count=%d < TP=%d: shrinking TP to %d and setting DP=1", device_count, tp, tp_eff)
        return build_parallelism_override(engine=engine, tp=tp_eff, dp=resolved_dp), notes

    if resolved_dp == template_dp:
        notes["device_count_status"] = "noop_equals_template"
        return {}, notes

    notes["device_count_status"] = "overridden"
    return build_parallelism_override(engine=engine, dp=resolved_dp), notes


# 通用 argv 引擎的固定策略链。特殊引擎可以通过 extension 替换整条链，避免
# MindIE 的 local_device_count 被公共 TP/DP 协调误解释。
TRANSFORMS: list[Transform] = [device_count_transform]


def _transforms_for_engine(engine: str | None) -> list[Transform]:
    """返回引擎声明的策略链；未声明时保持历史通用行为。"""
    extension = get_engine_extension(engine or "")
    if extension.post_template_transforms is not None:
        return list(extension.post_template_transforms)
    return TRANSFORMS


def requires_parallelism_preflight(engine: str) -> bool:
    """判断当前策略链是否会执行公共 TP/DP 收缩预检。"""
    return device_count_transform in _transforms_for_engine(engine)


def post_template_strategy(engine_config: dict, ctx: dict[str, Any]) -> tuple[dict, dict]:
    """小策略层入口:按固定顺序跑 ``TRANSFORMS`` 链,汇总 override 与 notes。

    **不会原地修改** ``engine_config``;返回值由调用方统一合并。

    Args:
        engine_config: 选定 strategy 的模板 engine_config(只读)。
        ctx: 透传给各 transform 的上下文(如 ``device_count`` / ``topology``)。

    Returns:
        ``(overrides, notes)``:各 transform 结果的合并。
        两者都为空表示本层未改写参数。
    """
    overrides: dict = {}
    notes: dict = {}
    # 引擎差异只通过 extension 能力进入；公共策略层不导入 MindIE 领域实现。
    for transform in _transforms_for_engine(ctx.get("engine")):
        override, note = transform(engine_config, ctx)
        overrides.update(override)
        notes.update(note)
    return overrides, notes
