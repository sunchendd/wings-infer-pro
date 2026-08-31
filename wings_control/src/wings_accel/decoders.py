"""
SmartDecoding Expander — 智能投机解码方案选择与渲染。

重要关键点:
- enabled=false / 无草稿路径且未配置 methods → None,不产出 disabled 占位。
- **仅消费 YAML 显式声明的 draft 方案,代码不合成任何方案**(资产能力声明是唯一真相源):
  ① 草稿 architectures 命中资产声明的 draft_arch → 选专用方法(eagle3/eagle/dflash/dspark…);
  ② **专用草稿错配检测**:架构含已知专用方法关键字但资产未声明可消费它的方案 →
     关闭投机(None)+ warning(附补充建议)——专用草稿头不是完整 LM,喂给其他方法必崩;
  ③ 资产显式声明的通用草稿(未声明 draft_arch 的 model_based,如 name: draft_model) → 选它。
  都不满足 → warning + None(不降级 no_model、不内置合成、不拼未验证 argv)。
- **草稿仅支持本地挂载目录**:读不到本地 config.json(HF repo id/未挂载/不可读)
  → warning + None,不猜架构、不当普通 draft。
- 无草稿路径 → no_model 分支(mtp/suffix,至多一个取首序);无 no_model 方案 → None。
- 草稿模型路径不在 Python 硬编码字段,由 YAML 中 $path/$draft_model_path 经 PlaceholderContext 渲染。
- **scenario 隔离**:yaml_loader 按 topology 路由出对应 scenario 子块(standalone/multi_node/
  pd_disaggregation.{prefill,decode})后才喂给本 expander;expander 只看扁平 decoding 列表,
  不感知 topology。PD 场景下 P 节点路由到的子块不含 decoding 键 → expander 拿到 None → 不产出。

处理流程:
1. enabled=false → None
2. 有草稿模型分支(model_path 归一后非空):
   - 读不到本地 config.json → warning + None(仅支持本地挂载草稿目录)
   - ① architectures 命中资产声明的 draft_arch → 选定专用方法
   - ② 架构含专用方法关键字但资产未声明该方法(①已 miss)→ None + warning
   - ③ 资产声明的通用草稿方案(draft_model 块)选定
   - 其余(含空占位资产)→ None + warning
3. 无草稿模型分支:
   - 无 methods → None
   - 筛 requires_model_path=false 且 eligible 的方案,取首序(至多一个)→ enabled
   - 空 → None
"""

import json
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from wings_accel.render import PlaceholderContext, render_scheme
from wings_accel.schemas import ModelConfig, SmartDecodingConfig, _FeatureOutput

logger = logging.getLogger(__name__)

# ② 专用草稿错配检测的关键字:草稿 config.json architectures 含这些关键字说明它是
# 某专用方法的草稿头(非完整小 LM)。资产未声明对应方法(draft_arch ①已 miss)时,
# 该草稿不可安全喂给其他方法 → 关闭投机并提示补资产。
# 只影响保守性:漏加新关键字最多让该草稿走 ③(资产声明)或 None,不会错放。
# dspark 是双形态方法:DeepSeek 系用内置权重(无草稿),Kimi-K3 需外部草稿
# (requires_model_path=true + draft_arch 含 dspark/k3dspark),故列入。
# ernie_mtp 属 no-model 方案(读主 checkpoint 内置 MTP 权重,见 smart-yaml SKILL),
# 不消费外部草稿路径,故不列入专用关键字。
_DEDICATED_DRAFT_KEYWORDS: tuple = ("eagle3", "eagle", "dflash", "dspark", "k3dspark")


def _keyword_in_arch(keyword: str, architecture: str) -> bool:
    """关键字是否命中草稿架构名(双向数字边界匹配,非普通子串)。

    普通子串 ``kw in arch`` 会让前缀包含关系误命中(eagle 匹配 eagle3、
    dspark 匹配 k3dspark;eagle-only 资产遇 Eagle3LlamaForCausalLM 草稿会
    错误产出 method: eagle)。改用
    ``(?<!\\d)kw(?!\\d)`` 双向数字边界:关键字紧邻数字即视为另一方法名
    (eagle3/k3dspark),不再命中裸关键字(eagle/dspark);CamelCase 连写的
    真实架构名(mistraleagleforcausallm / deepseekv2forcausallmeagle)不受影响。
    输入两侧均假设已小写归一。

    Args:
        keyword: draft_arch / 守卫名单关键字(小写)。
        architecture: 草稿 config.json 架构名(小写)。

    Returns:
        是否命中。
    """
    return re.search(rf"(?<!\d){re.escape(keyword)}(?!\d)", architecture) is not None


def _read_draft_architectures(draft_path: str) -> List[str]:
    """读取草稿模型 config.json 的 architectures 字段(小写归一)。

    仅接受本地挂载的草稿模型**目录**(读其下 config.json)。传入 config.json 文件
    路径同样拒绝:原始输入会经 $path 渲染进 speculative_config.model,引擎需要的
    是模型目录,原样透传会启动失败。非目录/缺 config.json/解析失败 → 空列表
    (上层据此 warning + 关闭投机,不降级)。

    Args:
        draft_path: 草稿模型目录路径(SPECULATIVE_DECODE_MODEL_PATH)。

    Returns:
        architectures 列表(小写);读不到 → []。
    """
    if not draft_path:
        return []
    draft_dir = Path(draft_path)
    if not draft_dir.is_dir():
        return []
    config_file = draft_dir / "config.json"
    if not config_file.is_file():
        return []
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("failed to read draft config.json %s: %s", config_file, exc)
        return []
    archs = data.get("architectures") if isinstance(data, dict) else None
    if not isinstance(archs, list):
        return []
    return [str(a).lower() for a in archs]


def _match_draft_method(methods: List[Dict[str, Any]], architectures: List[str]) -> Optional[Dict[str, Any]]:
    """按草稿 architectures 匹配 draft-based 方案。

    每个 scheme 可选声明 ``draft_arch``(list,小写关键字)。匹配规则:
    scheme 的任一 draft_arch 关键字以**词边界**命中任一 architecture 字符串 → 命中
    (边界匹配防前缀误命中:eagle 不匹配 eagle3,dspark 不匹配 k3dspark)。
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
        if any(_keyword_in_arch(kw, arch) for kw in keywords for arch in architectures):
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
    # 草稿路径归一:none/null 字面量当空(MaaS 未填可能下发字面量)
    model_path = _normalize_optional_path(cfg.model_path)

    # Step [1]: 有草稿路径 → 仅消费 YAML 显式声明的方案(资产能力声明是唯一
    # 真相源,代码不合成):
    # ① 专用匹配 → ② 错配守卫 → ③ 资产通用草稿;其余 None。
    if model_path:
        model_based = [m for m in methods if _is_model_based(m)]
        archs = _read_draft_architectures(model_path)
        # 仅支持本地挂载草稿目录:读不到 config.json(HF repo id/未挂载/不可读/
        # 传了 config.json 文件路径)→ 不猜架构、不当普通 draft,关闭投机。
        if not archs:
            logger.warning(
                "decoding draft %s: local config.json unreadable (only locally mounted "
                "draft directories are supported); disabling speculative decoding",
                model_path,
            )
            return None
        matched = _match_draft_method(model_based, archs)
        # ① draft_arch 专用匹配(命中)
        if matched:
            logger.info("decoding draft: architectures=%s matched dedicated %s", archs, matched.get("name"))
            return render_scheme(matched, ctx, degraded=False)
        # ② 专用草稿错配检测:草稿架构含已知专用方法关键字但资产未声明可消费它的
        #    方案(①已 miss)。专用草稿头不是完整 LM,喂给其他方法必崩 → 关闭投机
        #    + warning,并给出补资产建议(能力缺口变成可行动的资产工单)。
        detected = sorted(kw for kw in _DEDICATED_DRAFT_KEYWORDS if any(_keyword_in_arch(kw, a) for a in archs))
        if detected:
            logger.warning(
                "decoding draft %s: architectures=%s indicate dedicated draft method(s) %s, "
                "but this asset declares no consumable scheme for them (declared: %s); "
                "disabling speculative decoding. To enable, add scheme block(s) declaring "
                "draft_arch with these keyword(s) once recipe/0day evidence exists",
                model_path,
                archs,
                detected,
                [m.get("name") for m in model_based] or "<none>",
            )
            return None
        # ③ 资产显式声明的通用草稿(如 name: draft_model,参数按模型调)
        generic_draft = [m for m in model_based if not m.get("draft_arch")]
        if generic_draft:
            logger.info(
                "decoding draft: architectures=%s; using declared generic draft %s",
                archs,
                generic_draft[0].get("name"),
            )
            return render_scheme(generic_draft[0], ctx, degraded=False)
        # 其余(含空占位资产):无声明则不开,不内置合成、不拼未验证 argv
        logger.warning(
            "decoding draft %s: architectures=%s match no declared scheme (declared: %s); "
            "disabling speculative decoding. To enable, declare a draft_model scheme "
            "or draft_arch block in the asset",
            model_path,
            archs,
            [m.get("name") for m in model_based] or "<none>",
        )
        return None

    # Step [2]: 无草稿路径 → no_model 分支(至多一个,取首序)
    # 未配置 decoding 块 / 无 methods → None(scenario 子块缺 decoding 键时也走这条)
    if not methods:
        return None
    no_models = [m for m in methods if not _is_model_based(m) and _eligible(m, cfg)]
    if no_models:
        if len(no_models) > 1:
            logger.warning(
                "decoding no_model matched %d schemes; no_model must have at most one, selecting the first",
                len(no_models),
            )
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
