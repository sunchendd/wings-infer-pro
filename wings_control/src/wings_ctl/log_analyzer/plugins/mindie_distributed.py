# -*- coding: utf-8 -*-
"""MindIE 分布式（Ascend）插件。

针对 MindIE 多节点分布式部署场景（Ascend NPU）的日志分析插件。
日志来源：通过 ``tail -F -q -n +1 /root/mindie/log/debug/*.log`` 聚合到
``/var/log/wings/mindie_sum.log``，由 log_analyzer 统一分析。

MindIE 日志格式有两种风格：
  - C++ 日志: ``[timestamp] [pid] [tid] [llm] [INFO] [file:line] message``
  - Python 日志: ``[timestamp] [pid] [tid] [llm] [INFO] [file-line] : message``

本插件中的正则仅匹配各日志行的特征部分（模块标签 + 文件名 + 关键消息），
不依赖时间戳或 PID，以保证跨版本兼容性。
"""

from __future__ import annotations

from typing import Dict, List

from .mindie_single import MindIESinglePlugin


def _make_offset_calc(orig_fn, offset, ceiling):
    """创建带偏移量和上界的进度计算函数。

    Args:
        orig_fn: 原始进度计算函数
        offset: 进度偏移量
        ceiling: 进度上界

    Returns:
        调整后的进度计算函数
    """

    def adjusted_calc(match, curr):
        return min(orig_fn(match, curr) + offset, ceiling)

    return adjusted_calc


class MindIEDistributedPlugin(MindIESinglePlugin):
    """MindIE 分布式 Ascend 插件 - 继承自单机插件，增加分布式特有阶段。

    适配 MindIE 引擎在昇腾 NPU 上的多节点分布式部署场景。
    阶段划分（仅 master 节点运行分析器）：
      init(5%) → hccl_init(5%) → distributed_setup(5%) → accel_enabling(15%) →
      engine_booting(10%) → model_loading(30%) → model_compiling(32%) →
      server_checking(6%) → ready(2%)
    """

    def get_stage_definitions(self) -> Dict[str, Dict]:
        """返回阶段定义和权重。"""
        # 合并阶段定义，保持与单机版本相同的权重
        # init: 5%
        # hccl_init: 5%
        # distributed_setup: 5%
        # accel_enabling: 15%
        # engine_booting: 10%
        # model_loading: 30%
        # model_compiling: 32%
        # server_checking: 6%
        # ready: 2%

        return {
            "init": {"weight": 5, "name": "wings-control初始化"},
            "hccl_init": {"weight": 5, "name": "HCCL分布式初始化"},
            "distributed_setup": {"weight": 5, "name": "分布式环境配置"},
            "accel_enabling": {"weight": 15, "name": "加速特性注入"},
            "engine_booting": {"weight": 10, "name": "MindIE引擎启动"},
            "model_loading": {"weight": 30, "name": "模型加载"},
            "model_compiling": {"weight": 32, "name": "模型编译"},
            "server_checking": {"weight": 6, "name": "服务启动"},
            "ready": {"weight": 2, "name": "启动终态"},
        }

    def get_log_patterns(self) -> List[Dict]:
        """返回日志匹配模式。"""
        patterns = super().get_log_patterns()

        # 添加分布式特有模式
        distributed_patterns = [
            {"pattern": r"export RANK_TABLE_FILE=", "phase_code": "hccl_init", "progress_calc": 8},
            {"pattern": r"chmod 640 .*hccl_ranktable\.json", "phase_code": "hccl_init", "progress_calc": 10},
            {"pattern": r"export HCCL_WHITELIST_DISABLE=1", "phase_code": "hccl_init", "progress_calc": 12},
            {"pattern": r"Setting up distributed environment", "phase_code": "distributed_setup", "progress_calc": 15},
            {"pattern": r"Distributed environment ready", "phase_code": "distributed_setup", "progress_calc": 18},
        ]

        # 调整后续阶段的进度值
        # accel_enabling: 18-30%
        # engine_booting: 30-40%
        # model_loading: 40-70%
        # model_compiling: 70-92%
        # server_checking: 92-98%
        # ready: 100%

        # 更新现有模式的进度计算
        for pattern in patterns:
            if pattern["phase_code"] == "engine_booting":
                if isinstance(pattern["progress_calc"], int):
                    pattern["progress_calc"] = min(30 + (pattern["progress_calc"] - 20), 40)
            elif pattern["phase_code"] == "model_loading":
                if isinstance(pattern["progress_calc"], int):
                    pattern["progress_calc"] = min(40 + (pattern["progress_calc"] - 30), 70)
            elif pattern["phase_code"] == "model_compiling":
                if isinstance(pattern["progress_calc"], int):
                    pattern["progress_calc"] = min(70 + (pattern["progress_calc"] - 60), 92)
            elif pattern["phase_code"] == "server_checking":
                if isinstance(pattern["progress_calc"], int):
                    pattern["progress_calc"] = min(92 + (pattern["progress_calc"] - 92), 98)

        return distributed_patterns + patterns

    def get_error_patterns(self) -> List[Dict]:
        """返回错误匹配模式。"""
        patterns = super().get_error_patterns()

        # 添加分布式特有错误模式
        distributed_errors = [
            {
                "pattern": r"The size of npuDeviceIds \(subset\) does not equal to worldSize",
                "error_type": "MindIENpuDeviceIdsMismatch",
            },
            {"pattern": r"HCCL communi[ca]+tion error", "error_type": "HCCLError"},
            {"pattern": r"Ray cluster initialization failed", "error_type": "RayInitFailed"},
            {"pattern": r"Worker registration timeout", "error_type": "WorkerTimeout"},
            {"pattern": r"Connection refused", "error_type": "ConnectionRefused"},
        ]

        return patterns + distributed_errors
