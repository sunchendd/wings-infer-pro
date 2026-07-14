"""wings_accel 独立入口。

重要关键点:
- 自闭环入口:仅依赖 engine/version/hardware/model 入参与 smart-accel YAML,不依赖外部解析状态。
- 调用链为定位 YAML → 构造 SmartAccelInput → func_smart_accel → SmartAccelOutput。
- 找不到匹配 YAML 返回 None,语义是 smart accel no-op,不是异常。
- config_root 可覆盖包内配置,用于测试或外部部署;默认回落到随包分发的 smart-accel。
"""

from pathlib import Path
from typing import Optional, Union

from wings_accel.core import func_smart_accel
from wings_accel.schemas import SmartAccelOutput
from wings_accel.yaml_loader import LoadFlags, load_smart_accel_from_config


def resolve_smart_accel_from_config(
    *,
    engine: str,
    engine_version: str,
    hardware_family: str,
    model_name: str,
    flags: Optional[LoadFlags] = None,
    config_root: Union[str, Path] = "",
) -> Optional[SmartAccelOutput]:
    """从入参与包内配置完成 SmartAccel 解析并返回输出。

    Args:
        engine: 引擎名(vllm / vllm_ascend / sglang ...)。
        engine_version: 引擎版本,可带或不带 v 前缀。
        hardware_family: 硬件目录名,如 rtx_pro_5000_72G。
        model_name: 模型名,用于扫描匹配 smart-accel YAML。
        flags: MaaS/CLI 开关覆盖;缺省使用 LoadFlags() 默认值。
        config_root: 可选外部配置根目录;缺省使用包内 smart-accel。

    Returns:
        SmartAccelOutput: 成功匹配并解析时返回。
        None: 未找到匹配 YAML 时返回,表示 smart accel no-op。
    """
    smart_input = load_smart_accel_from_config(
        config_root,
        engine,
        engine_version,
        hardware_family,
        model_name,
        flags,
    )
    if smart_input is None:
        return None
    return func_smart_accel(smart_input)
