"""
CustomFeatures Expander — 自定义启动参数方案。

custom_features 是 smart_accel 里与 decoding/kv_offload/sparse 正交的【自由特性】段,
用于表达引擎级杂项开关(如 Mamba prefix caching 的 --mamba-cache、--trust-remote-code 等)
及其环境变量,这些不属于三大特性但又需要随模型下发。

重要关键点:
- 本 expander 不做特性门控;是否调用由 core 决定。
- block 必须是非空 list,否则返回 None。
- 所有有效方案均 always-on;cli_params 深合并、envs 后者覆盖前者。
- scheme 名拼接所有方案 name,用于 diagnostics,不影响渲染。

方案结构:
    - name:       方案名(写入诊断)
    - cli_params: 任意键值对,由 render 渲染(bool/scalar/dict/list 均可)
    - envs:       环境变量

行为:所有方案均 always-on,深合并各自 cli_params 后一次性渲染,合并进同一个 EngineParams。
由 core 控制:仅当 decoding/kv_cache/sparse 至少一项产出时才调用本 expander。
"""

from typing import Any, Dict, Optional

from wings_accel.render import (
    PlaceholderContext,
    deep_merge_dicts,
    extract_packages,
    fill_envs,
    render_engine_config,
)
from wings_accel.schemas import EngineParams, _FeatureOutput


def smart_custom_features_expander(
    block: Any,
    ctx: PlaceholderContext,
) -> Optional[_FeatureOutput]:
    # 未配置 / 非 list / 空 → None
    if not isinstance(block, list) or not block:
        return None

    merged_cli: Dict[str, Any] = {}
    merged_env: Dict[str, Any] = {}
    names = []
    packages = []
    for s in block:
        if not isinstance(s, dict):
            continue
        if s.get("name"):
            names.append(str(s["name"]))
        deep_merge_dicts(merged_cli, s.get("cli_params") or {})
        merged_env.update(s.get("envs") or {})
        packages.extend(extract_packages(s))

    if not merged_cli and not merged_env:
        return None

    engine_params = EngineParams(
        env=fill_envs(merged_env, ctx),
        engine_config=render_engine_config(merged_cli, ctx),
    )
    scheme = " + ".join(names) if names else "custom_features"
    return _FeatureOutput(scheme=scheme, engine_params=engine_params, packages=packages)
