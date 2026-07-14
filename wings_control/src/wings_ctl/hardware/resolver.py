"""HardwareResolver — 读 hardware_info.json 产出 HardwareContext。

输入: hardware_info.json 文件路径 (str)
输出: HardwareContext

hardware_family 参与目录定位;gpu/driver/cuda/cann 等字段携带进 audit,不参与逻辑分支。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional, Union

from wings_ctl.core.models import HardwareContext

logger = logging.getLogger(__name__)

# hardware_family 尾部的显存后缀,如 "H100_80G" 的 "_80G"。大小写无关(config 变体目录用大写 G)。
_GPU_MEM_SUFFIX = re.compile(r"_(\d+)G$", re.IGNORECASE)


def parse_gpu_mem_suffix(hardware_family: str) -> Optional[int]:
    """从 hardware_family 尾部 _<N>G 后缀解析单卡显存 GB。

    这是 gpu_mem 的唯一来源:MaaS 把单卡物理显存编码在 hardware_family 后缀里
    (如 "H100_80G" → 80),供单机 TP 收缩显存闸使用。不带后缀 = 未提供显存。

    Args:
        hardware_family: 硬件族下发值(可能带 _<N>G 后缀)。

    Returns:
        显存 GB 整数;无后缀返回 None。
    """
    match = _GPU_MEM_SUFFIX.search(hardware_family)
    return int(match.group(1)) if match else None


def strip_gpu_mem_suffix(hardware_family: str) -> str:
    """去掉 hardware_family 尾部的 _<N>G 显存后缀,返回卡型基名。

    与 parse_gpu_mem_suffix 同用一条正则(单一判定点):普通卡的显存后缀是冗余信息,
    目录定位时剥掉后用裸卡名匹配(如 "H100_80G" → "H100");无后缀原样返回。

    Args:
        hardware_family: 硬件族下发值。

    Returns:
        去掉显存后缀的卡型基名。
    """
    return _GPU_MEM_SUFFIX.sub("", hardware_family)


def resolve_hardware(hardware_info_path: Union[str, Path]) -> HardwareContext:
    """从 hardware_info.json 解析硬件环境。

    Args:
        hardware_info_path: JSON 文件路径。

    Returns:
        HardwareContext 实例。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: JSON 缺少必要字段。
    """
    path = Path(hardware_info_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("hardware_info.json must be a JSON object")

    hardware_family = data.get("hardware_family")
    if not hardware_family:
        raise ValueError("hardware_info.json missing required field 'hardware_family'")

    device = data.get("device", "nvidia")

    logger.info(
        "HardwareResolver: family=%s device=%s",
        hardware_family, device,
    )

    return HardwareContext(
        hardware_family=hardware_family,
        device=device,
        gpu_mem_gb=parse_gpu_mem_suffix(hardware_family),
        raw=data,
    )
