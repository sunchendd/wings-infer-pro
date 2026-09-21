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
from wings_accel.yaml_loader import (
    LoadFlags,
    is_package_smart_accel_source,
    load_smart_accel_from_config,
)


def _has_pre_serve_commands(output: SmartAccelOutput) -> bool:
    """判断 SmartAccel 输出是否包含会写入启动脚本的启动前命令。"""
    return bool(
        output.pre_serve
        or output.pre_serve_master
        or output.pre_serve_client
    )


def resolve_smart_accel_from_config(
    *,
    engine: str,
    engine_version: str,
    hardware_family: str,
    model_name: str,
    flags: Optional[LoadFlags] = None,
    config_root: Union[str, Path] = "",
    gpu_count: int = 1,
) -> Optional[SmartAccelOutput]:
    """从入参与包内配置完成 SmartAccel 解析并返回输出。

    Args:
        engine: 引擎名(vllm / vllm_ascend / sglang ...)。
        engine_version: 引擎版本,可带或不带 v 前缀。
        hardware_family: 硬件目录名,如 rtx_pro_5000_72G。
        model_name: 模型名,用于扫描匹配 smart-accel YAML。
        flags: MaaS/CLI 开关覆盖;缺省使用 LoadFlags() 默认值。
        config_root: 可选外部配置根目录;缺省使用包内 smart-accel。
        gpu_count: 卡数;load 之前写入 flags(估算在 load 内部)。

    Returns:
        SmartAccelOutput: 成功匹配并解析时返回。
        None: 未找到匹配 YAML 时返回,表示 smart accel no-op。
    """
    if flags is None:
        flags = LoadFlags()
    flags.gpu_count = int(gpu_count or 1)
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
    # hardware_family 是部署权威硬件(smart-accel YAML 常无 hardware_profile 块);覆盖 gpu_type,
    # 使 SystemConfig.gpu_type 对齐部署硬件族(端口/协议现由 YAML 资产明文声明,不再据此派生)。
    smart_input.hardware_config.gpu_type = hardware_family
    # gpu_count(device_count)用于按卡均分容量(mooncake global_segment_size / memcache dram.size);
    # smart-accel YAML 无 hardware_profile → 默认 1,需由调用方(apply_smart_accel 的 device_count)透传。
    if gpu_count and gpu_count > 0:
        smart_input.hardware_config.gpu_count = gpu_count
    output = func_smart_accel(smart_input)
    if _has_pre_serve_commands(output):
        output.pre_serve_trusted = is_package_smart_accel_source(
            smart_input.source_file
        )
    return output
