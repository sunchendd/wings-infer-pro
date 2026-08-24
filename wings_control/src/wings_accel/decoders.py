"""
SmartDecoding Expander — 智能投机解码方案选择与渲染。

重要关键点:
- enabled=false、未配置 methods、无合格方案都返回 None,不产出 disabled 占位。
- 有草稿路径时按草稿模型 config.json 的 architectures 字段匹配 draft-based 方案
  (eagle3/dflash/dspark/draft);无草稿路径走 no_model 方案(mtp/suffix)兜底。
- model_based 多方案时按 draft_arch 匹配 architectures 选定;未匹配到任何
  draft_arch → 降级到 draft(通用草稿方案,若声明);无 draft → 降级 no_model。
- model_based 未命中时降级到 no_model,并设置 degraded/degrade_reason 供 core 写诊断。
- no_model 方案至多声明一个(无草稿投机只有一种),取首序;多声明时 warning 取首序。
- 草稿模型路径不在 Python 硬编码字段,由 YAML 中 $path/$draft_model_path 经 PlaceholderContext 渲染。
- **scenario 隔离**:yaml_loader 按 topology 路由出对应 scenario 子块(standalone/multi_node/
  pd_disaggregation.{prefill,decode})后才喂给本 expander;expander 只看扁平 decoding 列表,
  不感知 topology。PD 场景下 P 节点路由到的子块不含 decoding 键 → expander 拿到 None → 不产出。

处理流程:
1. enabled=false / 未配置 / 无 methods → None
2. 有草稿模型分支(model_path 非空):
   - 读草稿 config.json architectures → 按 draft_arch 匹配 draft-based 方案
   - 命中 → 选定;未命中 draft_arch 但有通用 draft 方案 → 选 draft
   - 都未命中 → 降级到 no_model(requires_model_path=false,至多一个,取首序)
3. 无草稿模型分支 / 降级落点:
   - 筛 requires_model_path=false 且 eligible 的方案,取首序(至多一个)→ enabled
   - 空 → None
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from wings_accel.render import PlaceholderContext, render_scheme
from wings_accel.schemas import ModelConfig, SmartDecodingConfig, _FeatureOutput

logger = logging.getLogger(__name__)


def _read_draft_architectures(draft_path: str) -> List[str]:
    """读取草稿模型 config.json 的 architectures 字段(小写归一)。

    草稿路径可能是本地目录(含 config.json)或 HF repo id(本地无文件)。
    本地有 config.json → 读 architectures;读不到(非本地/无文件/解析失败)→ 空列表
    (上层据此降级到 draft 通用方案或 no_model)。

    Args:
        draft_path: 草稿模型路径(SPECULATIVE_DECODE_MODEL_PATH)。

    Returns:
        architectures 列表(小写);读不到 → []。
    """
    if not draft_path:
        return []
    p = Path(draft_path)
    cfg = p / "config.json" if p.is_dir() else p
    if not cfg.is_file():
        return []
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("failed to read draft config.json %s: %s", cfg, exc)
        return []
    archs = data.get("architectures") if isinstance(data, dict) else None
    if not isinstance(archs, list):
        return []
    return [str(a).lower() for a in archs]


def _match_draft_method(
    methods: List[Dict[str, Any]], architectures: List[str]
) -> Optional[Dict[str, Any]]:
    """按草稿 architectures 匹配 draft-based 方案。

    每个 scheme 可选声明 ``draft_arch``(list,小写关键字)。匹配规则:
    scheme 的任一 draft_arch 关键字出现在任一 architecture 字符串里 → 命中。
    多个命中取首序(yaml 应保证 draft_arch 互斥)。

    Args:
        methods: draft-based 方案列表(已过滤 requires_model_path=true)。
        architectures: 草稿模型 architectures(小写)。

    Returns:
        命中的方案;无命中 → None。
    """
    if not architectures:
        return None
    for m in methods:
        draft_arch = m.get("draft_arch")
        if not draft_arch:
            continue  # 未声明 draft_arch 的不参与架构匹配(走通用 draft 兜底)
        if isinstance(draft_arch, str):
            draft_arch = [draft_arch]
        if not isinstance(draft_arch, list):
            continue
        keywords = [str(k).lower() for k in draft_arch]
        if any(kw in arch for kw in keywords for arch in architectures):
            return m
    return None


def smart_decoding_expander(
    cfg: SmartDecodingConfig,
    model: ModelConfig,
    block: Any,
    ctx: PlaceholderContext,
    topology: Optional[str] = None,
) -> Optional[_FeatureOutput]:
    """智能投机解码方案选择与渲染。

    scenario 隔离由 yaml_loader 完成(按 topology 路由出对应 scenario 子块),本函数
    只消费扁平 decoding 列表,不感知 topology。``topology`` 参数仅作向后兼容保留
    (旧调用约定),不再参与过滤。

    Args:
        cfg: 投机解码配置(enabled + 草稿路径)。
        model: 主模型元数据(model_arch 选草稿)。
        block: decoding 方案列表(已路由到当前 scenario 子块)。
        ctx: 占位符上下文。
        topology: **已废弃**(scenario 路由在 loader 完成);保留参数向后兼容。

    Returns:
        _FeatureOutput(选中 scheme + 渲染后 EngineParams);无可选 → None。
    """
    # 开关没开 → None(不产出 disabled 占位)
    if not cfg.enabled:
        return None

    methods = _as_methods(block)
    # 未配置 decoding 块 / 无 methods → None(scenario 子块缺 decoding 键时也走这条)
    if not methods:
        return None

    # 草稿路径归一:none/null 字面量当空(MaaS 未填可能下发字面量)
    model_path = _normalize_optional_path(cfg.model_path)
    # Step [1]: model_based branch(有草稿路径)——按 config.json architectures 匹配
    if model_path:
        model_based = [m for m in methods if _is_model_based(m) and _eligible(m, cfg)]
        if model_based:
            # 读草稿 config.json architectures → 按 draft_arch 匹配
            archs = _read_draft_architectures(model_path)
            matched = _match_draft_method(model_based, archs)
            if matched:
                logger.info("decoding model_based: draft architectures=%s matched %s", archs, matched.get("name"))
                return render_scheme(matched, ctx, degraded=False)
            # 未匹配 draft_arch → 降级到通用 draft 方案(未声明 draft_arch 的 model_based)
            generic_draft = [m for m in model_based if not m.get("draft_arch")]
            if generic_draft:
                logger.info("decoding model_based: architectures=%s did not match draft_arch; falling back to generic draft", archs)
                return render_scheme(generic_draft[0], ctx, degraded=False)
            # 无通用 draft → 降级到 no_model
            logger.info("decoding model_based: architectures=%s have no match or generic draft; falling back to no_model", archs)
        # miss -> 降级到 no_model(至多一个,取首序)
        no_models = [m for m in methods if not _is_model_based(m) and _eligible(m, cfg)]
        if no_models:
            if len(no_models) > 1:
                logger.warning("decoding no_model matched %d schemes; no_model must have at most one, selecting the first", len(no_models))
            return render_scheme(no_models[0], ctx, degraded=True, degrade_reason="model_based_miss->no_model")

    # Step [2]: no_model branch(或降级落点;至多一个,取首序)
    no_models = [m for m in methods if not _is_model_based(m) and _eligible(m, cfg)]
    if no_models:
        if len(no_models) > 1:
            logger.warning("decoding no_model matched %d schemes; no_model must have at most one, selecting the first", len(no_models))
        return render_scheme(no_models[0], ctx, degraded=False)

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


def _normalize_optional_path(raw: str) -> str:
    """草稿路径归一:空 / none / null(大小写不敏感)→ 空串。

    MaaS 下发 SPECULATIVE_DECODE_MODEL_PATH 时,用户未填可能下发字面量 "none"/"null";
    若当真实路径,eagle3 等 requires_model_path 方案会产出 model:"none" 致 vllm serve
    启动失败。在此(消费点)统一判定。
    """
    val = (raw or "").strip()
    return "" if val.lower() in ("none", "null") else val


def _eligible(method: Dict[str, Any], cfg: SmartDecodingConfig) -> bool:
    """requires_model_path 的方案仅当草稿路径非空才可选。"""
    if method.get("requires_model_path") and not _normalize_optional_path(cfg.model_path):
        return False
    return True



