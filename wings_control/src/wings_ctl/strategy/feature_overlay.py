"""FeatureOverlay:把特性开关转换成引擎参数覆盖层。

输入来自两部分:
1. 用户是否开启某个特性开关;
2. model.yaml 中 ``features.<key>.args`` 的参数模板。

本模块不直接改模板,而是返回 override 层给外层合并。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from wings_ctl.engines.param_names import flag_to_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeatureOverlayResult:
    """特性参数覆盖、来源链和处理说明。"""

    overrides: dict[str, Any]
    trace_sources: dict[str, tuple[str, str]]
    notes: dict[str, str]


# 开关(engine_config canonical key) -> yaml features key
# 这里只处理 tool_calling / reasoning。spec_decoding 由 wings-accel 处理。
_SWITCH_TO_FEATURE: dict[str, str] = {
    "enable_auto_tool_choice": "tool_calling",
    "enable_auto_think_choice": "reasoning",
}


def parse_feature_args(args: list[str]) -> dict[str, Any]:
    """把 ``features.<key>.args`` 反解成 engine_config 键值对。

    规则:
    - ``--flag value`` -> ``{"flag": "value"}``
    - 裸 ``--flag`` -> ``{"flag": True}``

    该函数只服务本模块接管的特性参数。

    Args:
        args: vllm CLI token 列表,如 ``["--enable-auto-tool-choice", "--tool-call-parser", "glm45"]``。

    Returns:
        engine_config 键 dict,如 ``{"enable_auto_tool_choice": True, "tool_call_parser": "glm45"}``。
        空列表 / None → ``{}``。
    """
    result: dict[str, Any] = {}
    if not args:
        return result
    i = 0
    n = len(args)
    while i < n:
        token = str(args[i])
        if not token.startswith("--"):
            # 遇到非 flag 游离 token 时仅告警并跳过,不阻断流程。
            logger.warning("features.args 出现非 flag 游离 token,已跳过:%r", token)
            i += 1
            continue
        key = flag_to_key(token)
        # 看下一个 token:存在且不是新 flag → 当值(kv);否则当裸 flag(True)。
        if i + 1 < n and not str(args[i + 1]).startswith("--"):
            result[key] = str(args[i + 1])
            i += 2
        else:
            result[key] = True
            i += 1
    return result


def feature_overlay_transform(engine_config: dict, ctx: dict[str, Any]) -> FeatureOverlayResult:
    """根据开关生成特性覆盖层。

    判定逻辑:
    - 无 features 或无开关 -> 返回空覆盖层;
    - 开关开了但 yaml 缺参数 -> 记录 warning 并跳过;
    - 开关开了且 yaml 有参数 -> 反解并加入覆盖层。

    Args:
        engine_config: 保留参数,用于和其它 transform 统一签名(本函数不读取)。
        ctx: 上下文,至少含:
            - ``features``: model.yaml 顶层 `features` 块(dict,可能为 None/缺失)。
            - ``feature_switches``: 已开启的开关 dict,如 ``{"enable_auto_tool_choice": True}``
              (来自 user_cli;值为 falsy/缺失视为未开)。

    Returns:
        ``(override_layer, notes)``:
            - override_layer: 特性补充的 engine_config 键;空 dict 表示无改动。
            - notes: 每个特性的处理结果,用于 audit/resolution_notes。
    """
    features = ctx.get("features") or {}
    switches = ctx.get("feature_switches") or {}
    override: dict[str, Any] = {}
    trace_sources: dict[str, tuple[str, str]] = {}
    notes: dict[str, str] = {}

    for switch_key, feature_key in _SWITCH_TO_FEATURE.items():
        if not switches.get(switch_key):
            continue

        feature = features.get(feature_key)
        args = (feature or {}).get("args")
        if not args:
            # 开关开了但 yaml 没这特性: 记录 warning,不中断流程。
            notes[f"feature_overlay.{feature_key}"] = f"switch_on_but_absent(switch={switch_key})"
            logger.warning(
                "特性开关 %s 已开,但 model.yaml features.%s 缺失或无 args,跳过(warn-skip)",
                switch_key,
                feature_key,
            )
            continue

        parsed = parse_feature_args(args)
        override.update(parsed)
        source_file = (
            str(ctx.get("reasoning_source_file") or "<strategy:feature>")
            if feature_key == "reasoning"
            else str(ctx.get("tool_calling_source_file") or "<strategy:feature>")
        )
        source_prefix = str(ctx.get("reasoning_source_path") or "strategy.feature.reasoning") if feature_key == "reasoning" else "features.tool_calling.args"
        for key in parsed:
            trace_path = (
                source_prefix
                if feature_key == "reasoning" and ctx.get("reasoning_source_path")
                else f"{source_prefix}.{key}"
            )
            trace_sources[key] = (source_file, trace_path)
        notes[f"feature_overlay.{feature_key}"] = "applied: " + " ".join(str(a) for a in args)
        logger.info(
            "特性覆盖生效:%s(开关 %s)→ 附加 %s",
            feature_key,
            switch_key,
            parsed,
        )

    return FeatureOverlayResult(
        overrides=override,
        trace_sources=trace_sources,
        notes=notes,
    )
