# -*- coding: utf-8 -*-
"""MindIE 单机（Ascend）插件。

针对 MindIE 单机部署场景（Ascend NPU）的日志分析插件。
日志来源：通过 ``tail -F -q -n +1 /root/mindie/log/debug/*.log`` 聚合到
``/var/log/wings/mindie_sum.log``，由 log_analyzer 统一分析。

MindIE 聚合日志中包含来自多个模块（llm / llmmodels / server）的日志行，
本插件仅匹配各阶段的关键消息文本，不依赖时间戳、PID、日志级别或源文件行号，
以保证跨版本兼容性和可读性。
"""

from __future__ import annotations

from typing import Dict, List

from ..log_analyzer import BaseLogPatternPlugin


class MindIESinglePlugin(BaseLogPatternPlugin):
    """MindIE 单机 Ascend 插件。

    适配 MindIE 引擎在昇腾 NPU 上的单机部署场景。
    阶段划分：
      init(5%) → accel_enabling(15%) → engine_booting(10%) →
      model_loading(30%) → model_compiling(32%) → server_checking(6%) → ready(2%)
    """

    def get_error_patterns(self) -> List[Dict]:
        """返回错误匹配模式。"""
        return [
            {"pattern": r"ConfigManager init exception", "error_type": "MindIEConfigError"},
            {"pattern": r"Failed to initialize BackendConfig from JSON", "error_type": "MindIEConfigError"},
            {"pattern": r"\[mindie\] ERROR: daemon exited with code", "error_type": "MindIEDaemonFailed"},
            {"pattern": r"Traceback \(most recent call last\):", "error_type": "Exception"},
            {"pattern": r"RuntimeError:", "error_type": "RuntimeError"},
            {"pattern": r"Aborted \(core dumped\)", "error_type": "CoreDump"},
            {"pattern": r"OOM|out of memory|Cannot allocate memory", "error_type": "OOM"},
        ]

    def get_stage_definitions(self) -> Dict[str, Dict]:
        """返回阶段定义和权重。"""
        return {
            "init": {"weight": 5, "name": "wings-control初始化"},
            "accel_enabling": {"weight": 15, "name": "加速特性注入"},
            "engine_booting": {"weight": 10, "name": "MindIE引擎启动"},
            "model_loading": {"weight": 30, "name": "模型加载"},
            "model_compiling": {"weight": 32, "name": "模型编译"},
            "server_checking": {"weight": 6, "name": "服务启动"},
            "ready": {"weight": 2, "name": "启动终态"},
        }

    def get_log_patterns(self) -> List[Dict]:
        """返回日志匹配模式。"""
        patterns = []
        patterns.extend(self._get_engine_booting_patterns())
        patterns.extend(self._get_model_loading_patterns())
        patterns.extend(self._get_model_compiling_patterns())
        patterns.extend(self._get_server_checking_patterns())
        patterns.extend(self._get_ready_patterns())
        return patterns

    def _get_engine_booting_patterns(self) -> List[Dict]:
        """获取 engine_booting 阶段的日志模式。

        对应 MindIE 启动早期的 C++/Python 初始化日志，
        包括 LLMRuntime 初始化、模型部署配置、Executor 初始化等。
        """
        return [
            {
                "pattern": r"ModelDeployConfig::vocabSize=",
                "phase_code": "engine_booting",
                "progress_calc": 20,
            },
            {
                "pattern": r"LLMRuntime init success!",
                "phase_code": "engine_booting",
                "progress_calc": 22,
            },
            {
                "pattern": r"InitModelConfig:",
                "phase_code": "engine_booting",
                "progress_calc": 24,
            },
            {
                "pattern": r"Executor instance init",
                "phase_code": "engine_booting",
                "progress_calc": 26,
            },
            {
                "pattern": r"init base config",
                "phase_code": "engine_booting",
                "progress_calc": 28,
            },
            {
                "pattern": r"Start dynamic config handler success",
                "phase_code": "engine_booting",
                "progress_calc": 30,
            },
        ]

    def _get_model_loading_patterns(self) -> List[Dict]:
        """获取 model_loading 阶段的日志模式。

        对应 MindIE 模型加载过程，包括设备设置、tokenizer 初始化、
        模型初始化、模型传输到设备、模型加载完成等。
        """
        return [
            {
                "pattern": r"model_runner\.config:",
                "phase_code": "model_loading",
                "progress_calc": 32,
            },
            {
                "pattern": r"Current process is setting device npu:",
                "phase_code": "model_loading",
                "progress_calc": 35,
            },
            {
                "pattern": r"init tokenizer done",
                "phase_code": "model_loading",
                "progress_calc": 40,
            },
            {
                "pattern": r"Initialized model:",
                "phase_code": "model_loading",
                "progress_calc": 50,
            },
            {
                "pattern": r"Start transferring model to device",
                "phase_code": "model_loading",
                "progress_calc": 55,
            },
            {
                "pattern": r"Model successfully transferred to device",
                "phase_code": "model_loading",
                "progress_calc": 60,
            },
        ]

    def _get_model_compiling_patterns(self) -> List[Dict]:
        """获取 model_compiling 阶段的日志模式。

        对应 MindIE 模型编译过程，包括 prefill warmup 和 decode warmup。
        模型编译是 MindIE 启动中耗时较长的阶段，分配较大权重。
        """
        return [
            {
                "pattern": r"Successfully loaded model:",
                "phase_code": "model_compiling",
                "progress_calc": 60,
            },
            {
                "pattern": r"Before prefill warmup",
                "phase_code": "model_compiling",
                "progress_calc": 72,
            },
            {
                "pattern": r"After prefill warmup",
                "phase_code": "model_compiling",
                "progress_calc": 82,
            },
            {
                "pattern": r"After Decode warmup",
                "phase_code": "model_compiling",
                "progress_calc": 92,
            },
        ]

    def _get_server_checking_patterns(self) -> List[Dict]:
        """获取 server_checking 阶段的日志模式。

        对应 MindIE 服务启动阶段，包括模型初始化完成、引擎线程启动、
        endpoint 启动等。
        """
        return [
            {
                "pattern": r"model init success",
                "phase_code": "server_checking",
                "progress_calc": 92,
            },
            {
                "pattern": r"model initialized\.",
                "phase_code": "server_checking",
                "progress_calc": 94,
            },
            {
                "pattern": r"LlmEngine init succeeds!",
                "phase_code": "server_checking",
                "progress_calc": 96,
            },
            {
                "pattern": r"Start endpoint success",
                "phase_code": "server_checking",
                "progress_calc": 98,
            },
        ]

    def _get_ready_patterns(self) -> List[Dict]:
        """获取 ready 阶段的日志模式。

        对应 MindIE 服务完全就绪，daemon 启动成功。
        """
        return [
            {
                "pattern": r"Daemon start success!",
                "phase_code": "ready",
                "progress_calc": 100,
            },
        ]
