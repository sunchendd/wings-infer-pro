# -*- coding: utf-8 -*-
"""日志分析器主模块 - 实时监控推理服务部署进度。

该模块提供插件化的日志分析能力，支持多种推理引擎和部署场景。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] WINGS-CONTROL [%(name)s#%(funcName)s:%(lineno)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("log_analyzer")


@dataclass
class AccelFeatureData:
    """加速特性数据封装。"""

    feature: str
    status: str
    progress: int
    message: str
    error_type: str = ""
    error_msg: str = ""


class StageProgress:
    """阶段进度管理器 - 负责写入和更新进度信息。"""

    def __init__(self, progress_file: str, start_time: datetime):
        """初始化进度管理器。

        Args:
            progress_file: 进度文件路径
            start_time: 启动时间
        """
        self.progress_file = progress_file
        self.start_time = start_time
        self._ensure_files_exist()

    def write_progress(self, phase_code: str, phase_name: str, status: str, progress: int, key_log: str, **kwargs):
        """写入进度信息到JSONL文件。

        Args:
            phase_code: 阶段代码
            phase_name: 阶段名称
            status: 状态 (running/completed/failed)
            progress: 进度百分比 (0-100)
            key_log: 关键日志信息
            **kwargs: 额外字段
        """
        curr_time = datetime.now(tz=timezone.utc)
        elapsed_time = int((curr_time - self.start_time).total_seconds())

        data = {
            "progress": progress,
            "phase_code": phase_code,
            "phase_name": phase_name,
            "status": status,
            "key_log": key_log,
            "curr_time": curr_time.isoformat(),
            "start_time": self.start_time.isoformat(),
            "elapsed_time_s": elapsed_time,
            **kwargs,
        }

        try:
            with open(self.progress_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            logger.info("[Progress] %s%% - %s - %s", progress, phase_name, status)
        except OSError as e:
            logger.error("Failed to write progress file: %s", e)

    def _ensure_files_exist(self):
        """确保文件目录存在。"""
        Path(self.progress_file).parent.mkdir(parents=True, exist_ok=True)


class BaseLogPatternPlugin:
    """基础日志模式插件接口 - 所有插件必须继承此类。"""

    def __init__(self, config: Dict[str, Any]):
        """初始化插件。

        Args:
            config: 配置字典
        """
        self.config = config
        self.engine = config.get("engine", "vllm")
        self.deployment_mode = config.get("deployment_mode", "single")
        self.hardware = config.get("hardware", "nvidia")

    def get_error_patterns(self) -> List[Dict]:
        """返回错误匹配模式。

        Returns:
            错误模式列表，每个模式包含:
            - pattern: 正则表达式
            - error_type: 错误类型
        """
        logger.debug(
            "Using base error patterns for engine=%s mode=%s",
            self.engine,
            self.deployment_mode,
        )
        return []

    def get_stage_definitions(self) -> Dict[str, Dict]:
        """返回阶段定义和权重。

        Returns:
            阶段定义字典，格式: {phase_code: {weight, name}}
        """
        raise NotImplementedError

    def get_log_patterns(self) -> List[Dict]:
        """返回日志匹配模式。

        Returns:
            日志模式列表，每个模式包含:
            - pattern: 正则表达式
            - phase_code: 对应的阶段代码
            - progress_calc: 进度计算函数或固定值
        """
        raise NotImplementedError


class PatternPluginManager:
    """模式插件管理器 - 负责选择和管理插件。"""

    # 插件映射表
    PLUGIN_MAPPING = {
        ("vllm", "single", "nvidia"): "VLLMSingleGPUPlugin",
        ("vllm", "distributed", "nvidia"): "VLLMSingleGPUPlugin",
        ("vllm-ascend", "single", "ascend"): "VLLMAscendSinglePlugin",
        ("vllm-ascend", "distributed", "ascend"): "VLLMAscendSinglePlugin",
        ("sglang", "single", "nvidia"): "SGLangSingleGPUPlugin",
        ("mindie", "single", "ascend"): "MindIESinglePlugin",
        ("mindie", "distributed", "ascend"): "MindIEDistributedPlugin",
    }

    def __init__(self, config: Dict[str, Any]):
        """初始化插件管理器。

        Args:
            config: 配置字典
        """
        self.config = config
        self.plugin = self._load_plugin()

    def _load_plugin(self) -> BaseLogPatternPlugin:
        """根据配置加载合适的插件。

        Returns:
            插件实例
        """
        engine = self.config.get("engine", "vllm")
        deployment_mode = self.config.get("deployment_mode", "single")
        hardware = self.config.get("hardware", "nvidia")

        key = (engine, deployment_mode, hardware)
        plugin_class_name = self.PLUGIN_MAPPING.get(key)

        if not plugin_class_name:
            logger.warning("No matching plugin found: %s, using default vLLM single GPU plugin", key)
            plugin_class_name = "VLLMSingleGPUPlugin"

        # log_analyzer 在引擎容器中通过共享卷运行，模块路径为顶层包名
        # ``log_analyzer``（见 start_command.sh: ``cd /shared-volume && python3 -B -m log_analyzer.log_analyzer``）。
        from log_analyzer.plugins import (  # noqa: F811
            VLLMSingleGPUPlugin,
            VLLMAscendSinglePlugin,
            SGLangSingleGPUPlugin,
            MindIEDistributedPlugin,
            MindIESinglePlugin,
        )

        plugin_classes = {
            "VLLMSingleGPUPlugin": VLLMSingleGPUPlugin,
            "VLLMAscendSinglePlugin": VLLMAscendSinglePlugin,
            "SGLangSingleGPUPlugin": SGLangSingleGPUPlugin,
            "MindIEDistributedPlugin": MindIEDistributedPlugin,
            "MindIESinglePlugin": MindIESinglePlugin,
        }

        plugin_class = plugin_classes.get(plugin_class_name, VLLMSingleGPUPlugin)
        logger.info("Loading plugin: %s", plugin_class_name)
        return plugin_class(self.config)


class LogAnalyzer:
    """日志分析器主类 - 负责实时解析日志并更新进度。"""

    def __init__(self, config: Dict[str, Any], log_file: str, progress_file: str):
        """初始化日志分析器。

        Args:
            config: 配置字典
            log_file: 日志文件路径
            progress_file: 进度文件路径
        """
        self.config = config
        self.log_file = log_file
        self.start_time = datetime.now(tz=timezone.utc)

        # 初始化进度管理器
        self.stage_progress = StageProgress(progress_file, self.start_time)

        # 加载插件
        self.plugin_manager = PatternPluginManager(config)
        self.plugin = self.plugin_manager.plugin

        # 获取阶段定义
        self.stage_definitions = self.plugin.get_stage_definitions()

        # 获取日志模式
        self.log_patterns = self.plugin.get_log_patterns()
        self.error_patterns = self.plugin.get_error_patterns()

        # 添加通用阶段的日志模式（与加速引擎无关）
        self._add_common_patterns()

        # 统一编译所有正则表达式（包括通用模式）
        self._compile_patterns()

        # 状态跟踪
        self.current_phase = None
        self.current_progress = 0
        self.is_completed = False
        self.last_log_time = time.time()
        self.timeout_seconds = 300  # 5分钟超时
        self.elapsed_time = 0  # 累计超时秒数，供 _check_timeout 使用
        self._max_total_timeout = 1800  # 30分钟累计超时上限（仅告警，不判定失败）
        self._catching_up = False  # 追赶历史内容期间跳过错误模式，避免旧日志误报
        self.backend_port = str(config.get("backend_port", os.getenv("BACKEND_PORT", "17000")))

        # 写入初始状态
        self._write_initial_state()

    @staticmethod
    def _get_init_patterns() -> List[Dict]:
        """返回 init 阶段（wings-control 初始化）的日志模式列表。"""
        return [
            {"pattern": r"\[launcher\] Starting subprocess proxy", "phase_code": "init", "progress_calc": 3},
            {"pattern": r"\[launcher\] Starting subprocess health", "phase_code": "init", "progress_calc": 5},
        ]

    @staticmethod
    def _get_accel_enabling_patterns() -> List[Dict]:
        """返回 accel_enabling 阶段（加速特性注入）的日志模式列表。

        模式对齐 wings-accel 的关键日志。
        本方法覆盖安装启动、逐个操作与收尾/异常全过程。

        进度语义（accel_enabling 阶段内单调递增，10→20）：
        - 10: 加速安装开始（Installing patches / Installing for engine）
        - 12: 匹配到引擎补丁版本
        - 14/16: 包安装进行中 / 单个包安装完成
        - 18: 引擎补丁已应用
        - 20: 安装完成（或 install.py 缺失的异常兜底）
        """
        return [
            {
                "pattern": r"\[wings-accel\] Installing patches from /accel-volume",
                "phase_code": "accel_enabling",
                "progress_calc": 10,
            },
            {
                "pattern": r"\[wings-accel\] Installing for engine '.*?' \(extras: \[.*?\]\) \.\.\.",
                "phase_code": "accel_enabling",
                "progress_calc": 10,
            },
            {
                "pattern": r"\[wings-accel\] Matched engine patch version: \S+",
                "phase_code": "accel_enabling",
                "progress_calc": 12,
            },
            {
                "pattern": r"\[wings-accel\] Installing package: \S+",
                "phase_code": "accel_enabling",
                "progress_calc": 14,
            },
            {
                "pattern": r"\[wings-accel\] Package installed: \S+",
                "phase_code": "accel_enabling",
                "progress_calc": 16,
            },
            {
                "pattern": r"\[wings-accel\] Engine patches applied: engine=\S+",
                "phase_code": "accel_enabling",
                "progress_calc": 18,
            },
            {
                "pattern": r"\[wings-accel\] wings-accel installation complete",
                "phase_code": "accel_enabling",
                "progress_calc": 20,
            },
            {
                "pattern": r"\[wings-accel\] WARNING: /accel-volume/install.py not found",
                "phase_code": "accel_enabling",
                "progress_calc": 20,
            },
        ]

    def run(self):
        """运行日志分析器。"""
        logger.info("Starting log file monitoring: %s", self.log_file)

        if not self._wait_for_log_file():
            return

        logger.info("Log file created, starting analysis")

        try:
            self._monitor_log_file()
        except Exception as e:
            self._handle_analyzer_error(e)

    def _probe_backend_health(self) -> bool:
        """主动探测后端健康端点，确认引擎是否真正就绪。

        在 server_checking 阶段超时时调用：日志文件可能因 grep 过滤
        而不再有新内容，但引擎实际已正常运行。此方法通过直接 HTTP
        请求确认后端状态，避免误报"启动超时"。

        Returns:
            True 表示后端已就绪，False 表示不可达或未就绪
        """
        backend_host = os.getenv("BACKEND_HOST", "127.0.0.1")
        url = f"http://{backend_host}:{self.backend_port}/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    logger.info("backend health probe succeeded: %s (HTTP 200)", url)
                    return True
        except Exception as exc:
            logger.debug("backend health probe failed: %s (%s)", url, exc)
        return False

    def _wait_for_log_file(self) -> bool:
        """等待日志文件创建。

        Returns:
            是否成功等待到文件创建
        """
        max_wait = 600  # 最多等待600秒
        waited = 0
        while not os.path.exists(self.log_file):
            if waited >= max_wait:
                logger.error("log file %s not created within %d seconds, giving up waiting", self.log_file, max_wait)
                self.stage_progress.write_progress(
                    phase_code="init",
                    phase_name="wait_log_file",
                    status="warning",
                    progress=0,
                    key_log=f"Log file {self.log_file} not created within {max_wait}s",
                )
                return False
            logger.info("Waiting for log file creation: %s (waited %ds)", self.log_file, waited)
            time.sleep(1)
            waited += 1
        return True

    def _monitor_log_file(self):
        """监控日志文件并解析内容。"""
        with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
            self._read_existing_content(f)
            self._monitor_new_content(f)

    def _read_existing_content(self, file_handle):
        """读取日志文件中已有的内容。

        追赶阶段仅解析进度模式，跳过错误模式匹配。这样即使 rm -f
        未能清理旧日志，历史中的错误行也不会立即触发误报。
        真正的启动错误将在后续实时监控阶段被捕获。

        Args:
            file_handle: 文件句柄
        """
        self._catching_up = True
        for line in file_handle:
            self._parse_log_line(line)
            self.last_log_time = time.time()
        self._catching_up = False

    def _monitor_new_content(self, file_handle):
        """持续监控日志文件的新内容。

        Args:
            file_handle: 文件句柄
        """
        while not self.is_completed:
            line = file_handle.readline()
            if line:
                self._parse_log_line(line)
                self.last_log_time = time.time()
                self.elapsed_time = 0
            elif self._check_timeout():
                self._handle_timeout()
            else:
                time.sleep(0.1)

    def _handle_timeout(self):
        """处理超时情况。

        日志文件长时间无新内容时触发，用于确认引擎是否已实际就绪。
        日志无更新可能因：引擎已就绪后日志被 grep 过滤（health/metrics
        请求行被剔除），或引擎处于长时间编译阶段，或当前引擎的
        server_checking 阶段日志模式未匹配（进度无法到达 99%）。

        因此超时后无条件主动探测后端健康端点——后端 /health 返回 200
        即代表服务已可用，直接标记为 completed 收口，避免反复输出超时
        告警。探测失败则继续监控，写入 warning 级别信息性记录。

        超时本身不判定部署失败：部署失败由 health_router 状态机通过
        启动宽限期超时（STARTUP_GRACE_MS）返回 502 独立判定。
        """
        # 引擎启动完成后日志被过滤导致无新内容 → 主动探测后端
        if self._probe_backend_health():
            self.is_completed = True
            ready_name = self.stage_definitions.get("ready", {}).get("name", "ready")
            self.stage_progress.write_progress(
                phase_code="ready",
                phase_name=ready_name,
                status="completed",
                progress=100,
                key_log="Backend health probe OK - service confirmed running",
            )
            return

        # 超时仅告警，不判定失败；失败判定由 health_router 状态机负责
        if self.elapsed_time >= self._max_total_timeout:
            logger.warning(
                "cumulative timeout %d seconds exceeds the maximum limit of %d seconds",
                self.elapsed_time,
                self._max_total_timeout,
            )

        self.stage_progress.write_progress(
            phase_code=self.current_phase or "timeout",
            phase_name="startup_timeout",
            status="warning",
            progress=self.current_progress,
            key_log=f"Log file not updated for {self.elapsed_time} seconds",
        )

    def _handle_analyzer_error(self, error: Exception):
        """处理分析器异常。

        分析器自身异常不应判定部署失败：引擎可能仍在正常运行，
        仅分析器进程遇到解析错误。写入 warning 级别记录供诊断，
        部署状态由 health_router 状态机独立判定。

        Args:
            error: 异常对象
        """
        logger.error("Log analyzer error: %s", error)
        self.stage_progress.write_progress(
            phase_code="error",
            phase_name="analyzer_error",
            status="warning",
            progress=self.current_progress,
            key_log=str(error),
        )

    def _compile_patterns(self):
        """编译所有正则表达式模式。"""
        for pattern_info in self.log_patterns:
            pattern_info["compiled"] = re.compile(pattern_info["pattern"])

        for pattern_info in self.error_patterns:
            pattern_info["compiled"] = re.compile(pattern_info["pattern"])

    def _add_common_patterns(self):
        """添加通用阶段的日志模式（与加速引擎无关）。

        这些阶段包括：
        - init: wings-control初始化
        - accel_enabling: 加速特性注入
        """
        common_patterns = self._get_init_patterns() + self._get_accel_enabling_patterns()

        # 将通用模式添加到日志模式列表的开头
        self.log_patterns = common_patterns + self.log_patterns

    def _write_initial_state(self):
        """写入初始状态。"""
        self.stage_progress.write_progress(
            phase_code="init",
            phase_name="wings_control_init",
            status="running",
            progress=5,
            key_log="log_analyzer started",
        )

    def _check_timeout(self) -> bool:
        """检查是否超时。

        检测日志文件是否长时间无新内容。每次判定为超时后，
        将 ``last_log_time`` 推进到当前时刻，确保下一次超时
        判定至少间隔 ``timeout_seconds`` 秒，避免连续调用导致
        ``elapsed_time`` 在毫秒内从 300 跳涨至 1800 而误判。

        超时本身不判定部署失败，仅触发 _handle_timeout 写入 warning
        级别记录。部署失败由 health_router 状态机独立判定。

        Returns:
            是否超时
        """
        time_now = time.time()
        elapsed = time_now - self.last_log_time
        if elapsed > self.timeout_seconds:
            self.elapsed_time += self.timeout_seconds
            # 重置计时起点，确保下一次超时判定在 timeout_seconds 之后
            self.last_log_time = time_now
            logger.warning(
                "log file not updated for %s seconds, judged as timed out (cumulative %s seconds)",
                self.timeout_seconds,
                self.elapsed_time,
            )
            return True
        return False

    def _parse_log_line(self, line: str):
        """解析单行日志。

        错误模式匹配仅记录诊断信息（warning），不终止后续进度模式解析，
        也不判定部署失败。部署是否失败由 health_router 状态机通过实际
        HTTP 探测后端 /health 端点独立判定。

        Args:
            line: 日志行
        """
        if not self._catching_up:
            self._check_error_patterns(line)

        self._check_progress_patterns(line)

    def _check_error_patterns(self, line: str) -> None:
        """检查错误模式，匹配则记录诊断信息（warning，非终态）。

        log_analyzer 作为日志解析器，不具备判定部署是否失败的权威性：
        日志中的报错可能是非致命告警（如 deprecation traceback），
        也可能在后续被引擎自行恢复。部署失败应由 health_router 状态机
        通过实际 HTTP 探测后端 /health 端点独立判定（返回 502 start_failed）。

        因此本方法仅写入 status="warning" 的信息性记录，保留 error_type
        供诊断，不设置 is_failed，不写终态 failed，不终止后续进度解析。

        Args:
            line: 日志行
        """
        for pattern_info in self.error_patterns:
            match = pattern_info["compiled"].search(line)
            if match:
                self.stage_progress.write_progress(
                    phase_code=self.current_phase or "error",
                    phase_name="error_detected",
                    status="warning",
                    progress=self.current_progress,
                    key_log=line.strip(),
                    error_type=pattern_info.get("error_type", "unknown"),
                )
                return

    def _check_progress_patterns(self, line: str):
        """检查进度模式，匹配则更新阶段进度。

        Args:
            line: 日志行
        """
        for pattern_info in self.log_patterns:
            match = pattern_info["compiled"].search(line)
            if match:
                phase_code = pattern_info["phase_code"]
                stage_def = self.stage_definitions.get(phase_code, {})
                phase_name = stage_def.get("name", phase_code)

                progress = self._calc_progress(pattern_info, match)
                progress = max(progress, self.current_progress)
                self.current_phase = phase_code
                self.current_progress = progress

                self.stage_progress.write_progress(
                    phase_code=phase_code,
                    phase_name=phase_name,
                    status="running",
                    progress=progress,
                    key_log=line.strip(),
                )

                if phase_code == "ready":
                    self._mark_completed()
                return

    def _calc_progress(self, pattern_info: Dict, match) -> int:
        """根据模式配置计算进度值。

        Args:
            pattern_info: 模式配置字典
            match: 正则匹配对象

        Returns:
            计算后的进度值
        """
        progress_calc = pattern_info.get("progress_calc")
        if callable(progress_calc):
            return progress_calc(match, self.current_progress)
        if isinstance(progress_calc, (int, float)):
            return int(progress_calc)
        return self.current_progress

    def _mark_completed(self):
        """标记日志解析完成，不代表推理服务部署完成。"""
        self.is_completed = True
        ready_name = self.stage_definitions.get("ready", {}).get("name", "ready")
        self.stage_progress.write_progress(
            phase_code="ready",
            phase_name=ready_name,
            status="completed",
            progress=100,
            key_log="Log analyzer reached the ready pattern; service status is owned by FOA",
        )


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Wings-Infer Log Analyzer")
    parser.add_argument("--config", type=str, required=True, help="Analyzer config (JSON string)")
    parser.add_argument("--log-file", type=str, required=True, help="Log file path")
    parser.add_argument("--progress-file", type=str, required=True, help="Progress file path")
    return parser.parse_args()


def main():
    """主入口函数。"""
    args = parse_args()

    # 解析配置
    try:
        config = json.loads(args.config)
    except json.JSONDecodeError as e:
        logger.error("Configuration parse failed: %s", e)
        raise SystemExit(1) from e

    # 创建并运行分析器
    analyzer = LogAnalyzer(config=config, log_file=args.log_file, progress_file=args.progress_file)

    analyzer.run()


if __name__ == "__main__":
    main()
