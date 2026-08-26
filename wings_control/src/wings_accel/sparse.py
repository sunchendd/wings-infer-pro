"""
SmartSparse Expander — 智能稀疏化方案选择与渲染。

重要关键点:
- enabled=false、未配置、非 list、无合格 scheme 都返回 None。
- 每个 scheme 用 name 作为 sparse mode 门键(performance_first / accuracy_first)。
- performance_first 找不到时可降级到 accuracy_first,并设置 degraded/degrade_reason。
- 本模块不解释 hf_overrides/kv_cache_dtype 等参数内容,只选择方案并交给 render 渲染。

处理流程:
1. enabled=false / 未配置 / 无 scheme → None
2. 按 mode(performance_first/accuracy_first)匹配 scheme.name:
   - 命中 → enabled,取命中首个 scheme(mode 在 yaml 唯一,无需 priority)
3. performance_first 未命中 → 降级到 accuracy_first scheme(若存在)→ enabled(degraded)
4. 仍无命中 → None

scheme 结构(new):
    - name:        mode 门键(performance_first / accuracy_first)
    - cli_params:  任意键值对,由 render 渲染
    - envs:        环境变量

设计要点:
- 模块不解释 cli_params 内容,纯搬运 + 渲染;hf_overrides 等只是普通 flag。
- 输出 scheme 名就是命中的 name(如 "performance_first")。
"""

import logging
from typing import Any, Dict, List, Optional

from wings_accel.render import PlaceholderContext, extract_package_requirements, fill_envs, render_engine_config
from wings_accel.schemas import EngineParams, SmartKVSparseConfig, _FeatureOutput

logger = logging.getLogger(__name__)


def smart_sparse_expander(
    cfg: SmartKVSparseConfig,
    block: Any,
    ctx: PlaceholderContext,
) -> Optional[_FeatureOutput]:
    # 关闭 / 未配置 / 非 list → None
    if not cfg.enabled or not isinstance(block, list) or not block:
        return None

    schemes: List[Dict[str, Any]] = block
    requested_mode = cfg.mode

    matching = _matching_mode(schemes, requested_mode)
    if matching:
        # mode 在 yaml 唯一(performance_first / accuracy_first),取命中首个;多命中告警
        if len(matching) > 1:
            logger.warning(
                "sparse mode %r 命中 %d 个 scheme,取首个(yaml 应保证 mode 唯一)",
                requested_mode, len(matching),
            )
        scheme, mode_block = matching[0]
        return _render_sparse_scheme(scheme, mode_block, ctx, degraded=False)

    # 降级:performance_first -> accuracy_first
    if requested_mode == "performance_first":
        accuracy = _matching_mode(schemes, "accuracy_first")
        if accuracy:
            scheme, mode_block = accuracy[0]
            return _render_sparse_scheme(
                scheme,
                mode_block,
                ctx,
                degraded=True,
                degrade_reason="performance_first_miss->accuracy_first",
            )

    return None


def _matching_mode(schemes: List[Dict[str, Any]], mode: str) -> List[tuple[Dict[str, Any], Dict[str, Any]]]:
    return [(scheme, scheme) for scheme in schemes if scheme.get("name") == mode]


def _render_sparse_scheme(
    scheme: Dict[str, Any],
    mode_block: Dict[str, Any],
    ctx: PlaceholderContext,
    degraded: bool,
    degrade_reason: str = "",
) -> _FeatureOutput:
    engine_params = EngineParams(
        env=fill_envs(mode_block.get("envs") or {}, ctx),
        engine_config=render_engine_config(mode_block.get("cli_params") or {}, ctx),
    )
    return _FeatureOutput(
        scheme=str(scheme.get("name", "")),
        engine_params=engine_params,
        degraded=degraded,
        degrade_reason=degrade_reason,
        packages=extract_package_requirements(mode_block),
    )
