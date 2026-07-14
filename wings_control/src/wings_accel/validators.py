"""
输入检查层 — SmartAccel 用户意图提示。

重要关键点:
- 本层只收集轻量输入提示,不改变 SmartAccelInput,不 raise。
- 返回 warnings 列表,由 core.py 写日志;不进入 SmartAccelOutput。
- 适合放跨特性/用户意图提示,不适合放 YAML schema 强校验。

检查规则:
1. KV 卸载: 开磁盘必须先开内存；磁盘路径不能为空
2. 容量检查: disk_capacity_gb >= 0
3. 投机识别: 传了 draft model_path 但缺 model_arch 时告警
"""

from typing import List

from wings_accel.schemas import SmartAccelInput


def collect_smart_accel_warnings(inp: SmartAccelInput) -> List[str]:
    warnings: List[str] = []

    # KV offload: disk requires memory
    kv = inp.smart_kv_cache_config
    if kv.enabled and kv.disk_offload_enabled and not kv.memory_offload_enabled:
        warnings.append(
            "disk offload enabled but memory offload disabled; disk offload requires memory"
        )

    # KV offload: if disk on, disk_path should not be empty
    if kv.enabled and kv.disk_offload_enabled and not kv.disk_path:
        warnings.append("disk offload enabled but disk_path is empty")

    # KV offload: capacity sanity (>=0)
    if kv.enabled and kv.disk_offload_enabled and kv.disk_capacity_gb < 0:
        warnings.append("disk_capacity_gb must be >= 0")

    # Decoding: model_path non-empty but no model_arch -> warn
    dec = inp.smart_decoding_config
    if dec.enabled and dec.model_path and not inp.model_config.model_arch:
        warnings.append(
            "draft model path provided but model_arch missing; method identification may fail"
        )

    return warnings
