"""
冲突仲裁器 — 三特性方案选择间的兼容扩展点。

当前无硬编码冲突规则:decoding / kv_offload / sparse 可同时生效。
保留 resolve_conflicts 入口,避免 core 流水线形状随规则开关变化。
"""

from typing import Dict, Optional, Tuple

from wings_accel.schemas import _FeatureOutput


def resolve_conflicts(
    decoding: Optional[_FeatureOutput],
    sparse: Optional[_FeatureOutput],
    offload: Optional[_FeatureOutput],
    decoding_block,
    ctx,
) -> Tuple[Optional[_FeatureOutput], Optional[_FeatureOutput], Optional[_FeatureOutput], Dict[str, str]]:
    """返回原始特性输出;当前 MTP + LMCache/KV offload 不再冲突。"""
    return decoding, sparse, offload, {}
