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

    tp = engine_config.get("tensor_parallel_size", 1)
    template_dp = engine_config.get("data_parallel_size", 1)

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
        logger.info("device-count=%d < TP=%d:收缩 TP→%d、DP=1", device_count, tp, tp_eff)
        return {"tensor_parallel_size": tp_eff, "data_parallel_size": resolved_dp}, notes

    if resolved_dp == template_dp:
        notes["device_count_status"] = "noop_equals_template"
        return {}, notes

    notes["device_count_status"] = "overridden"
    return {"data_parallel_size": resolved_dp}, notes


# 固定顺序:当前仅 DeviceCount;后续追加 TopologyRuntimeInject / FeatureOverlay。
TRANSFORMS: list[Transform] = [device_count_transform]


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
    for transform in TRANSFORMS:
        override, note = transform(engine_config, ctx)
        overrides.update(override)
        notes.update(note)
    return overrides, notes
