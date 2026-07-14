"""
SmartDecoding Expander — 智能投机解码方案选择与渲染。

重要关键点:
- enabled=false、PD prefill、未配置 methods、无合格方案都返回 None,不产出 disabled 占位。
- cfg.model_path 非空时优先走 model_based 分支;requires_model_path=true 表示需要草稿模型。
- model_based 未命中时降级到 no_model,并设置 degraded/degrade_reason 供 core 写诊断。
- model_based 取首序(有草稿即选定,无需 priority);no_model 按 priority 取最高(mtp/suffix 兜底排序)。
- 草稿模型路径不在 Python 硬编码字段,由 YAML 中 $path/$draft_model_path 经 PlaceholderContext 渲染。

处理流程:
1. enabled=false / pd_role=prefill → None
2. 有草稿模型分支(model_path 非空):
   - 筛 requires_model_path=true 且 eligible 的方案,取首序 → enabled(model_based)
   - 未命中 → 跨类降级到 no_model(requires_model_path=false)方案中 priority 最高者
3. 无草稿模型分支 / 降级落点:
   - 筛 requires_model_path=false 且 eligible 的方案,按 priority 取最高 → enabled
   - 空 → None
"""

import logging
from typing import Any, Dict, List, Optional

from wings_accel.render import PlaceholderContext, render_scheme
from wings_accel.schemas import ModelConfig, SmartDecodingConfig, _FeatureOutput

logger = logging.getLogger(__name__)


def smart_decoding_expander(
    cfg: SmartDecodingConfig,
    model: ModelConfig,
    block: Any,
    ctx: PlaceholderContext,
    pd_role: Optional[str] = None,
) -> Optional[_FeatureOutput]:
    # 开关没开 / PD prefill 节点 → None(不产出 disabled 占位)
    if not cfg.enabled:
        return None
    if pd_role == "prefill":
        return None

    methods = _as_methods(block)
    # 未配置 decoding 块 / 无 methods → None
    if not methods:
        return None

    # Step [1]: model_based branch(有草稿路径)——有草稿即选定,取首序(无需 priority)
    if cfg.model_path:
        model_based = [m for m in methods if _is_model_based(m) and _eligible(m, cfg)]
        if model_based:
            if len(model_based) > 1:
                logger.warning(
                    "decoding model_based 命中 %d 个方案,取首序(有草稿即选定,yaml 应保证唯一)",
                    len(model_based),
                )
            return render_scheme(model_based[0], ctx, degraded=False)
        # miss -> 降级到 no_model
        no_models = [m for m in methods if not _is_model_based(m) and _eligible(m, cfg)]
        if no_models:
            best = _pick_priority(no_models)
            return render_scheme(best, ctx, degraded=True, degrade_reason="model_based_miss->no_model")

    # Step [2]: no_model branch(或降级落点)
    no_models = [m for m in methods if not _is_model_based(m) and _eligible(m, cfg)]
    if no_models:
        best = _pick_priority(no_models)
        return render_scheme(best, ctx, degraded=False)

    # 无合格方案 → None
    return None


def _as_methods(block: Any) -> List[Dict[str, Any]]:
    """decoding 块兼容两种写法:list 直接为方案序列;dict 取 methods。"""
    if isinstance(block, list):
        return block
    if isinstance(block, dict):
        methods = block.get("methods")
        return methods if isinstance(methods, list) else []
    return []


def _is_model_based(method: Dict[str, Any]) -> bool:
    """requires_model_path=true → model_based;否则 no_model。"""
    return bool(method.get("requires_model_path"))


def _eligible(method: Dict[str, Any], cfg: SmartDecodingConfig) -> bool:
    """requires_model_path 的方案仅当草稿路径非空才可选。"""
    if method.get("requires_model_path") and not cfg.model_path:
        return False
    return True


def _pick_priority(methods: List[Dict[str, Any]]) -> Dict[str, Any]:
    return max(methods, key=lambda m: m.get("priority") or 0)
