"""
=============================================================================
 Proxy 服务管理模块 (wings_control.py)
=============================================================================

功能概述：
    负责 proxy 和 health 两个 FastAPI 子服务的生命周期管理。
    不负责引擎脚本生成（由 cli.py 的 pipeline 负责）。

核心职责：
    1. 子服务托管
       - 启动并守护 proxy（反向代理）和 health（健康检查）两个 FastAPI 子服务
       - 监控子进程状态，异常退出时自动拉起（守护进程模式）
       - 处理系统信号（SIGINT/SIGTERM）实现优雅退出

    2. 分布式角色适配
       - Master: 启动 proxy + health（正常端口）
       - Worker: 仅启动 health（偏移端口 +1），BACKEND_URL 指向 Master

使用方式：
    from wings_ctl.wings_control import run
    sys.exit(run())
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
import threading
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import NamedTuple, Sequence

from wings_ctl.common.settings import settings
from wings_ctl.core.port_plan import PortPlan, derive_port_plan
from wings_ctl.utils.env_utils import env_bool, get_local_ip, get_master_ip
from wings_ctl.common.log_config import setup_root_logging, LOGGER_LAUNCHER
from wings_ctl.utils.noise_filter import install_noise_filters

setup_root_logging()
logger = logging.getLogger(LOGGER_LAUNCHER)

# 安装噪声过滤器：抑制 /health 访问日志、batch 噪声、pynvml FutureWarning
install_noise_filters()


@dataclass
class ManagedProc:
    """描述一个由 launcher 托管的子进程。

    这个数据类封装了子进程的完整元数据，用于 launcher 的进程守护循环。
    支持进程启动、停止、状态检查等生命周期操作。

    Attributes:
        name: 进程名称标识（如 'proxy'、'health'），用于日志和调试
        argv: 进程启动命令行参数列表，第一个元素通常是 python 解释器路径
        env:  进程环境变量字典，包含 BACKEND_URL、PORT 等运行时配置
        proc: subprocess.Popen 实例，进程未启动时为 None

    使用示例：
        >>> proxy = ManagedProc(
        ...     name='proxy',
        ...     argv=['python', '-m', 'uvicorn', 'proxy.gateway:app'],
        ...     env={'PORT': '18000', 'BACKEND_URL': 'http://127.0.0.1:17000'}
        ... )
        >>> _start(proxy)  # 启动进程
        >>> _stop(proxy)   # 停止进程
    """

    name: str           # 进程名称标识，用于日志打印
    argv: list[str]     # 命令行参数列表[python, -m, uvicorn, ...]
    env: dict[str, str] # 环境变量字典，继承自父进程并添加服务特定变量
    proc: subprocess.Popen | None = None  # 实际的子进程句柄
    dedupe_output: bool = False      # 是否过滤重复的 uvicorn worker 启动日志
    crash_count: int = 0            # 连续崩溃计数器
    last_start_ts: float = 0.0     # 上次启动时间戳
    backoff_until: float = 0.0     # 退避期截止时间戳


# Prometheus multi-process metrics 共享目录，放在日志共享卷下
_PROMETHEUS_MULTIPROC_DIR = "/var/log/wings/prometheus_multiproc"


# ---------------------------------------------------------------------------
# 子进程日志结构化中继
# ---------------------------------------------------------------------------


class ChildLogRelay(NamedTuple):
    """子进程日志中继数据结构。

    Attributes:
        logger_name: 目标 logger 名称（通常为 LOGGER_LAUNCHER）。
        level:       logging 级别常量。
        message:     日志消息文本。
        extra:       LogRecord extra 字段，供 WingsControlFormatter 使用。
    """
    logger_name: str
    level: int
    message: str
    extra: dict[str, str]


# 子进程日志时间戳正则（兼容有无毫秒部分）
_CHILD_TIMESTAMP_RE = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[,.]\d{3})?"

# 4 个正则覆盖新旧格式的所有变体
_CHILD_STRUCTURED_LOG_RES = (
    # 格式 1: [WINGS-CONTROL] 2026-07-22 10:00:01.456 [WARNING] [source] msg
    re.compile(
        r"^(?:\[WINGS-CONTROL\]\s+)?"
        rf"(?P<timestamp>{_CHILD_TIMESTAMP_RE})\s+"
        r"\[(?P<level>WARNING|ERROR|CRITICAL)\]\s+"
        r"\[(?P<source>[^\]]+)\]\s+"
        r"(?P<message>.*)$",
        re.IGNORECASE,
    ),
    # 格式 2: 2026-07-22 10:00:01.456 [WARNING] WINGS-CONTROL [source] msg
    re.compile(
        rf"^(?P<timestamp>{_CHILD_TIMESTAMP_RE})\s+"
        r"\[(?P<level>WARNING|ERROR|CRITICAL)\]\s+"
        r"WINGS-CONTROL\s+"
        r"\[(?P<source>[^\]]+)\]\s+"
        r"(?P<message>.*)$",
        re.IGNORECASE,
    ),
    # 格式 3: [WINGS-CONTROL][source] [WARNING] 2026-07-22 10:00:01.456 msg
    re.compile(
        r"^\[WINGS-CONTROL\]\[(?P<source>[^\]]+)\]\s+"
        r"\[(?P<level>WARNING|ERROR|CRITICAL)\]\s*"
        rf"(?P<timestamp>{_CHILD_TIMESTAMP_RE})\s+"
        r"(?P<message>.*)$",
        re.IGNORECASE,
    ),
    # 格式 4: 2026-07-22 10:00:01.456 [WINGS-CONTROL][source] [WARNING] msg
    re.compile(
        rf"^(?P<timestamp>{_CHILD_TIMESTAMP_RE})\s+"
        r"\[WINGS-CONTROL\]\[(?P<source>[^\]]+)\]\s+"
        r"\[(?P<level>WARNING|ERROR|CRITICAL)\]\s+"
        r"(?P<message>.*)$",
        re.IGNORECASE,
    ),
)

# 通用级别检测正则（非结构化日志）
_CHILD_LEVEL_RE = re.compile(
    r"\[(?P<bracket>WARNING|ERROR|CRITICAL)\]"
    r"|^(?P<prefix>WARNING|ERROR|CRITICAL):"
    r"|\b(?P<error>Traceback|Exception|Error:)",
    re.IGNORECASE,
)

# 级别名称 → logging 常量映射
_LOG_LEVELS = {
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "TRACEBACK": logging.ERROR,
    "EXCEPTION": logging.ERROR,
    "ERROR:": logging.ERROR,
}


def _normalize_child_log_line(
    proc_name: str,
    line: str,
) -> ChildLogRelay | None:
    """Parse a managed child-process log line for launcher relay.

    优先尝试结构化匹配（4 个正则覆盖新旧格式变体），
    匹配成功时保留子进程的原始时间戳、组件名和 source 信息。
    非结构化日志通过 _CHILD_LEVEL_RE 检测级别后转发。

    Args:
        proc_name: 子进程名称（如 'proxy'、'health'）。
        line:      子进程 stdout 原始行。

    Returns:
        解析成功返回 ChildLogRelay，否则返回 None（静默丢弃）。
    """
    text = line.rstrip()
    if not text:
        return None

    # 尝试结构化匹配
    structured = None
    for structured_log_re in _CHILD_STRUCTURED_LOG_RES:
        structured = structured_log_re.match(text)
        if structured:
            break
    if structured:
        level_name = structured.group("level").upper()
        return ChildLogRelay(
            LOGGER_LAUNCHER,
            _LOG_LEVELS.get(level_name, logging.WARNING),
            structured.group("message"),
            {
                "wings_child_component": proc_name,
                "wings_child_time": structured.group("timestamp"),
                "wings_child_source": structured.group("source"),
            },
        )

    # 非结构化日志：检测级别
    level_match = _CHILD_LEVEL_RE.search(text)
    if not level_match:
        return None

    level_name = (
        level_match.group("bracket")
        or level_match.group("prefix")
        or level_match.group("error")
        or "WARNING"
    ).upper()
    return ChildLogRelay(
        LOGGER_LAUNCHER,
        _LOG_LEVELS.get(level_name, logging.WARNING),
        text,
        {"wings_child_component": proc_name},
    )


# ---------------------------------------------------------------------------
# 进程生命周期管理
# ---------------------------------------------------------------------------


def _start_output_filter_thread(proc: ManagedProc) -> None:
    """启动守护线程，从子进程 stdout 读取并过滤低优先级日志。

    只转发 WARNING / ERROR / CRITICAL 级别的消息到 launcher 日志，
    所有 INFO 及以下级别（含 uvicorn worker 启动日志、proxy 应用日志）静默丢弃。
    这显著减少了多 worker 场景下的日志噪声。

    与旧版简单正则匹配不同，新版使用 _normalize_child_log_line() 进行
    结构化解析，支持：
    - 识别子进程已格式化的日志（保留原始时间戳和组件名）
    - 通过 WingsControlFormatter 格式化输出，避免重复前缀
    - 非结构化日志通过 _CHILD_LEVEL_RE 检测级别后转发
    """
    def _relay() -> None:
        try:
            for raw in iter(proc.proc.stdout.readline, b""):
                line = raw.decode("utf-8", errors="replace")
                relay = _normalize_child_log_line(proc.name, line)
                if relay is not None:
                    logging.getLogger(relay.logger_name).log(
                        relay.level,
                        relay.message,
                        extra=relay.extra,
                    )
        except (ValueError, OSError):
            pass

    t = threading.Thread(target=_relay, name=f"filter-{proc.name}", daemon=True)
    t.start()


def _start(proc: ManagedProc) -> None:
    """启动单个托管子进程。

    使用 subprocess.Popen 创建子进程，继承当前进程的标准输入输出。
    启动失败时仅记录错误日志，不抛出异常，允许守护循环继续尝试。

    Args:
        proc: 待启动的托管进程对象，启动后 proc.proc 将被设置为 Popen 实例

    注意事项:
        - 子进程使用指定的 env 字典作为环境变量，不会自动继承父进程变量
        - 启动失败通常是由于命令不存在或权限不足，需检查 argv[0] 路径
        - 启动成功后需要通过 poll() 检查进程是否正常运行
        - dedupe_output=True 时，stdout/stderr 重定向到过滤线程，
          仅保留一条 uvicorn worker 启动日志
    """
    logger.info("Starting subprocess %s: %s", proc.name, " ".join(proc.argv))
    try:
        if proc.dedupe_output:
            # 多 worker 场景：管道化输出并通过过滤线程去重
            proc.proc = subprocess.Popen(
                proc.argv, env=proc.env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            _start_output_filter_thread(proc)
        else:
            # 使用 Popen 创建子进程，env 参数完全替换（非继承）父进程环境
            proc.proc = subprocess.Popen(proc.argv, env=proc.env)
    except OSError as e:
        # OSError 通常表示可执行文件不存在或权限问题
        logger.error("Failed to start %s: %s", proc.name, e)


def _kill_process_forcefully(proc: ManagedProc) -> None:
    """向已超过 SIGTERM 等待期的进程发送 SIGKILL。

    等待最多 5 秒；若仍未退出则放弃并记录警告。
    在容器环境中，僵尸进程由 init 进程收割，影响较小。
    """
    logger.warning("%s did not respond to SIGTERM, sending SIGKILL", proc.name)
    proc.proc.kill()  # type: ignore[union-attr]
    try:
        proc.proc.wait(timeout=5)  # type: ignore[union-attr]
    except subprocess.TimeoutExpired:
        logger.warning("%s still running after SIGKILL, giving up", proc.name)


def _stop(proc: ManagedProc) -> None:
    """优雅停止托管子进程，必要时强制终止。

    采用两阶段停止策略：
    1. 首先发送 SIGTERM 信号请求优雅退出，等待最多 10 秒。
    2. 若进程未响应，调用 _kill_process_forcefully() 发送 SIGKILL。
    3. 若仍未退出，放弃等待并记录警告。

    Args:
        proc: 待停止的托管进程对象，停止后 proc.proc 将被置为 None
    """
    if not proc.proc:
        return  # 进程从未启动或已被清理

    if proc.proc.poll() is None:
        logger.info("Sending SIGTERM to %s (pid=%d)", proc.name, proc.proc.pid)
        proc.proc.terminate()
        try:
            proc.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _kill_process_forcefully(proc)
    proc.proc = None  # 清理引用


def _restart_if_needed(proc: ManagedProc) -> None:
    """检查进程状态，必要时自动重启（带崩溃循环保护）。

    该函数在主循环中周期性调用，实现子进程的自动恢复：
    - 进程从未启动 → 立即启动
    - 进程正在运行 → 不做操作
    - 进程已退出   → 记录退出码并重启（带指数退避）

    崩溃循环保护策略：
    - 进程在 30 秒内退出视为崩溃，连续崩溃计数器递增
    - 连续崩溃时指数退避：等待 min(2^crash_count, 60) 秒后再重启
    - 进程稳定运行超过 30 秒后退出，崩溃计数器重置
    """
    crash_threshold_sec = 30  # 小于此时间视为崩溃
    max_backoff_sec = 60      # 最大退避时间

    if not proc.proc:
        # 进程从未启动或已标记为待重启
        # 检查是否在退避等待期内（崩溃循环保护）
        if proc.backoff_until and time.time() < proc.backoff_until:
            return  # 退避期内，跳过本轮
        proc.last_start_ts = time.time()
        _start(proc)
        return

    # poll() 返回 None 表示进程仍在运行
    code = proc.proc.poll()
    if code is None:
        return  # 进程正常运行，无需操作

    # ── 进程已退出，记录崩溃/正常退出并清理句柄 ──
    uptime = time.time() - proc.last_start_ts if proc.last_start_ts else 0

    # 清理已退出进程句柄，下轮将通过 "not proc.proc" 分支重启
    proc.proc = None

    if uptime < crash_threshold_sec:
        # 短时间内退出视为崩溃
        proc.crash_count += 1
        backoff = min(2 ** proc.crash_count, max_backoff_sec)
        proc.backoff_until = time.time() + backoff
        logger.warning(
            "[Restart] %s exited abnormally (code=%s, uptime=%.1fs), "
            "crash_count=%d, waiting %ds before restart...",
            proc.name, code, uptime, proc.crash_count, backoff,
        )
        # 退避期内不重启，下轮若已过退避期则经 "not proc.proc" 分支启动
    else:
        # 稳定运行后退出，重置崩溃计数器并立即重启
        proc.crash_count = 0
        logger.warning("[Restart] %s exited (code=%s, uptime=%.1fs), resetting crash count and restarting immediately",
                       proc.name, code, uptime)
        proc.last_start_ts = time.time()
        _start(proc)


def _check_and_restart_all(processes: list[ManagedProc]) -> bool:
    """检查所有子进程状态，按需重启，返回是否全部已退出。"""
    all_dead = True
    for proc in processes:
        _restart_if_needed(proc)
        if proc.proc and proc.proc.poll() is None:
            all_dead = False
    return all_dead


def _daemon_loop(
    processes: list[ManagedProc],
    label: str,
) -> int:
    """信号处理 + 子进程守护循环（master/worker/standalone 共用）。"""
    stop_event = Event()

    def _on_signal(signum: int, _frame: object) -> None:
        logger.info("received signal: %s", signum)
        stop_event.set()

    # signal.signal() 只能在主线程中调用；加防御性检查避免未来重构时引入问题
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)
    else:
        logger.warning(
            "_daemon_loop called from non-main thread, "
            "signal handlers not registered"
        )

    exit_code = 0
    try:
        while not stop_event.is_set():
            if _check_and_restart_all(processes) and processes:
                logger.error("%s: all managed processes have exited", label)
                exit_code = 1
                break
            time.sleep(settings.PROCESS_POLL_SEC)
    finally:
        for proc in processes:
            _stop(proc)
        logger.info("%s shutdown complete", label)
    return exit_code


# ---------------------------------------------------------------------------
# 子进程构建
# ---------------------------------------------------------------------------


def _build_child_env(port_plan: PortPlan) -> dict[str, str]:
    """为 proxy/health 子进程准备环境变量。"""
    env = os.environ.copy()
    # 确保 PYTHONPATH 包含 src/wings_ctl/ 以便子进程能导入 proxy 模块。
    # proxy 模块位于 src/wings_ctl/proxy/，uvicorn 需要能找到顶层包 proxy。
    # 原仓库通过 wings_start.sh 的 PYTHONPATH 包含 APP_WORKDIR 来实现此效果，
    # 此处通过追加当前包的父目录来适配 refactor 仓库结构。
    _package_dir = str(Path(__file__).resolve().parent)
    _existing = env.get("PYTHONPATH", "")
    if _package_dir not in _existing.split(os.pathsep):
        env["PYTHONPATH"] = os.pathsep.join(
            [p for p in (_existing, _package_dir) if p]
        )

    # 后端地址：sidecar 与 engine 在同一 Pod 内共享网络命名空间。
    # 分布式模式下 RANK_IP（Pod IP）可直接访问 engine；
    # 单机/本地开发无 RANK_IP 时回退到 127.0.0.1。
    rank_ip = os.getenv("RANK_IP")
    backend_host = rank_ip if rank_ip else "127.0.0.1"

    env["BACKEND_URL"] = f"http://{backend_host}:{port_plan.backend_port}"
    env["BACKEND_HOST"] = backend_host
    env["BACKEND_PORT"] = str(port_plan.backend_port)
    env["PORT"] = str(port_plan.proxy_port)
    env["PROXY_PORT"] = str(port_plan.proxy_port)
    env["HEALTH_PORT"] = str(port_plan.health_port)
    env["HEALTH_SERVICE_PORT"] = str(port_plan.health_port)

    # 引擎类型：K8s 部署通过 ENGINE 环境变量传入（如 mindie/vllm/sglang），
    # 子进程（health_router/proxy/health_service）统一通过 ENGINE 读取。
    engine = os.getenv("ENGINE", "vllm")
    env["ENGINE"] = engine.strip().lower()

    # Prometheus 多进程指标汇总目录。
    # 当 proxy 以多 worker 模式运行时(--workers > 1)，prometheus_client
    # 需要此目录来汇总各 worker 进程的 Gauge/Counter 指标，否则 /metrics
    # 只能返回当前响应进程的部分数据。
    # 目录位于日志共享卷 /var/log/wings 下，engine 容器也使用同一路径。
    _ensure_prometheus_multiproc_dir()
    env["PROMETHEUS_MULTIPROC_DIR"] = _PROMETHEUS_MULTIPROC_DIR

    return env


def _ensure_prometheus_multiproc_dir() -> None:
    """确保 Prometheus 多进程目录存在且为空（清除上次残留的 .db 文件）。"""
    import shutil
    try:
        if os.path.isdir(_PROMETHEUS_MULTIPROC_DIR):
            shutil.rmtree(_PROMETHEUS_MULTIPROC_DIR)
        os.makedirs(_PROMETHEUS_MULTIPROC_DIR, exist_ok=True)
    except OSError as e:
        logger.warning("Failed to prepare PROMETHEUS_MULTIPROC_DIR=%s: %s",
                       _PROMETHEUS_MULTIPROC_DIR, e)


def _build_proxy_proc(
    port_plan: PortPlan, env: dict, python_bin: str, uvicorn_mod: str, proxy_workers: int
) -> "ManagedProc":
    """构建 proxy 进程的 ManagedProc 对象。"""
    # 仅打印 ERROR 级别到 stdout/stderr，完整日志由 RotatingFileHandler 写入文件。
    # 应用自身日志（wings-proxy / log-center）的 ERROR 仍可见。
    uvicorn_log_level = "error"
    proxy_argv = [
        python_bin, "-m", uvicorn_mod, settings.PROXY_APP,
        "--host", "0.0.0.0", "--port", str(port_plan.proxy_port),
        "--log-level", uvicorn_log_level,
    ]
    if proxy_workers > 1:
        proxy_argv += ["--workers", str(proxy_workers)]
        # 多 worker 场景下增大 TCP backlog，防止高并发时连接被拒
        proxy_argv += ["--backlog", "8192"]
    return ManagedProc(name="proxy", argv=proxy_argv, env=env.copy(), dedupe_output=(proxy_workers > 1))


def _build_health_proc(
    port_plan: PortPlan, env: dict, python_bin: str, uvicorn_mod: str
) -> "ManagedProc":
    """构建 health 进程的 ManagedProc 对象。"""
    return ManagedProc(
        name="health",
        argv=[
            python_bin, "-m", uvicorn_mod, settings.HEALTH_APP,
            "--host", "0.0.0.0", "--port", str(port_plan.health_port),
            "--log-level", "info",
        ],
        env=env.copy(),
    )


def _detect_cgroup_memory_mb() -> int | None:
    """读取 cgroup 内存限制（兼容 v1/v2），返回 MB；读取失败返回 None。"""
    paths = [
        "/sys/fs/cgroup/memory.max",                  # cgroup v2
        "/sys/fs/cgroup/memory/memory.limit_in_bytes", # cgroup v1
    ]
    for p in paths:
        try:
            raw = Path(p).read_text().strip()
            if raw == "max" or not raw.isdigit():
                continue
            val = int(raw)
            if val > 0:
                return val // (1024 * 1024)
        except (OSError, ValueError):
            continue
    return None


def _auto_proxy_workers(max_workers: int = 128) -> int:
    """根据容器内存限制自动计算最优 Worker 数。

    公式：workers = (可用内存MB - 200) / 65 - 2，结果夹在 [1, max_workers]。
    若无法读取 cgroup 限制（非容器环境），退回默认值 4。
    """
    mem_mb = _detect_cgroup_memory_mb()
    if mem_mb is None:
        return 4
    workers = int((mem_mb - 200) / 65) - 2
    workers = max(1, min(workers, max_workers))
    logger.info("Auto-detected cgroup memory limit: %d MB -> PROXY_WORKERS=%d", mem_mb, workers)
    return workers


def _build_processes(port_plan: PortPlan) -> list[ManagedProc]:
    """构造 launcher 需要托管的 proxy、health 进程。"""
    env = _build_child_env(port_plan)
    python_bin = settings.PYTHON_BIN
    uvicorn_mod = settings.UVICORN_MODULE

    # 确定 proxy worker 数量：
    # 1. 优先使用 PROXY_WORKERS 环境变量（用户显式指定）
    # 2. 未指定时自动读取 cgroup 内存限制计算最优值
    # 3. 非容器环境退回默认值 4
    # 上限 128：每个 worker 约 65MB RAM。
    max_proxy_workers = 128
    env_val = os.getenv("PROXY_WORKERS")
    if env_val is not None:
        proxy_workers = min(int(env_val), max_proxy_workers)
    else:
        proxy_workers = _auto_proxy_workers(max_proxy_workers)
    env["PROXY_WORKERS"] = str(proxy_workers)

    return [
        _build_proxy_proc(port_plan, env, python_bin, uvicorn_mod, proxy_workers),
        _build_health_proc(port_plan, env, python_bin, uvicorn_mod),
    ]


# ---------------------------------------------------------------------------
# 分布式角色判断
# ---------------------------------------------------------------------------


def _resolve_ip_or_self(ip: str) -> str:
    """尝试 DNS 解析 ip；解析失败时返回原始字符串。"""
    try:
        return socket.gethostbyname(ip)
    except socket.error as exc:
        logger.debug("DNS resolution failed for '%s': %s", ip, exc)
        return ip


def _ips_match(local_ip: str, master_ip: str) -> bool:
    """判断 local_ip 与 master_ip 是否指向同一节点（支持 DNS 解析）。

    优先做原始字符串比较（快速路径），匹配失败时再解析 DNS（慢速路径）。
    """
    if local_ip == master_ip:
        return True
    return _resolve_ip_or_self(local_ip) == _resolve_ip_or_self(master_ip)


def _determine_role() -> str:
    """判断当前 Pod 在分布式集群中的角色。

    通过 DISTRIBUTED 环境变量判断是否为分布式模式:
      - 非分布式 → "standalone"（沿用原有单机流程）
      - 分布式且 RANK_IP == MASTER_IP → "master"（含 DNS 解析）
      - 分布式且 RANK_IP != MASTER_IP → "worker"

    RANK_IP 由上层（MaaS）传入，每个 Pod 唯一，不依赖 NODE_RANK 环境变量。

    Returns:
        "standalone" | "master" | "worker"
    """
    distributed = env_bool("DISTRIBUTED", False)
    if not distributed:
        return "standalone"

    master_ip = get_master_ip()
    local_ip = get_local_ip()  # 来自 RANK_IP 环境变量

    if not master_ip:
        logger.warning("DISTRIBUTED=true but MASTER_IP not set, falling back to standalone")
        return "standalone"

    if _ips_match(local_ip, master_ip):
        local_r = _resolve_ip_or_self(local_ip)
        master_r = _resolve_ip_or_self(master_ip)
        logger.info(
            "Role determined: MASTER (RANK_IP=%s→%s, MASTER_IP=%s→%s)",
            local_ip, local_r, master_ip, master_r,
        )
        return "master"

    local_r = _resolve_ip_or_self(local_ip)
    master_r = _resolve_ip_or_self(master_ip)
    logger.info(
        "Role determined: WORKER (RANK_IP=%s→%s, MASTER_IP=%s→%s)",
        local_ip, local_r, master_ip, master_r,
    )
    return "worker"


def _load_distributed_config() -> dict:
    """加载 config/distributed_config.json 配置。"""
    config_path = Path(__file__).parent / "config" / "defaults" / "distributed_config.json"
    with open(config_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Master / Worker / Standalone 模式
# ---------------------------------------------------------------------------


def _run_master_mode(port_plan: PortPlan) -> int:
    """Master 模式：启动 proxy + health 子服务并进入守护循环。

    与 standalone 模式的区别：
    - Master 需要启动 Master API 协调服务（由 distributed 模块负责，此处不处理）
    - Master 需要等待 Worker 注册并分发启动指令（由 distributed 模块负责，此处不处理）
    - 本函数仅负责 proxy 和 health 的启动和守护
    """
    processes = _build_processes(port_plan)
    for proc in processes:
        _start(proc)

    logger.info(
        "Master mode running: backend=%d proxy=%d health=%d",
        port_plan.backend_port,
        port_plan.proxy_port,
        port_plan.health_port,
    )
    return _daemon_loop(processes, "Master mode")


def _run_worker_mode(port_plan: PortPlan) -> int:
    """Worker 模式：仅启动 health 子服务（偏移端口避免 hostNetwork 冲突）。

    Worker 不暴露 proxy（只有 Master 的 rank0 暴露），health 端口偏移 +1。
    BACKEND_URL 指向 Master 的 backend 端口。

    Worker 本地没有 engine API server（只运行 Ray worker），因此将
    BACKEND_URL 指向 Master 的 backend 端口。分布式场景下，Master backend
    健康即表示包含此 Worker 的 Ray 集群正常工作。
    """
    master_ip = get_master_ip()
    worker_health_port = port_plan.health_port + 1
    master_backend_url = f"http://{master_ip}:{port_plan.backend_port}"

    worker_port_plan = PortPlan(
        enable_proxy=port_plan.enable_proxy,
        backend_port=port_plan.backend_port,
        proxy_port=port_plan.proxy_port,
        health_port=worker_health_port,
    )
    # Worker 只启动 health 服务，不启动 proxy
    processes = [p for p in _build_processes(worker_port_plan) if p.name == "health"]
    for proc in processes:
        proc.env["BACKEND_URL"] = master_backend_url
        _start(proc)
    logger.info(
        "Worker health probing master backend at %s",
        master_backend_url,
    )

    logger.info(
        "Worker mode running: health=%d "
        "(waiting for master to dispatch engine start)",
        worker_health_port,
    )
    return _daemon_loop(processes, "Worker mode")


def _run_standalone_mode(port_plan: PortPlan) -> int:
    """Standalone 模式：启动 proxy + health 子服务并进入守护循环。"""
    processes = _build_processes(port_plan)
    for proc in processes:
        _start(proc)

    logger.info(
        "proxy service running: backend=%s proxy=%s health=%s",
        port_plan.backend_port,
        port_plan.proxy_port,
        port_plan.health_port,
    )
    return _daemon_loop(processes, "standalone")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def run(argv: Sequence[str] | None = None) -> int:
    """启动并守护 proxy 和 health 子服务。

    cli.py:main() 已完成配置解析和脚本生成，本函数仅负责：
    1. 判断当前分布式角色（standalone/master/worker）
    2. 根据角色构建对应的端口规划和进程列表
    3. 启动子进程并进入守护循环
    """
    # 从环境变量获取端口配置（cli.main() 已经设置好 PORT、HEALTH_PORT 等）
    port = int(os.getenv("PORT", "18000"))
    health_port = int(os.getenv("HEALTH_PORT", "19000"))

    port_plan = derive_port_plan(
        port=port,
        enable_reason_proxy=settings.ENABLE_REASON_PROXY,
        health_port=health_port,
    )

    # 当前版本必须启用 proxy。
    if not port_plan.enable_proxy:
        logger.error("ENABLE_REASON_PROXY=false is not supported in v4 MVP")
        return 2

    # ---- 分布式角色分支 ----
    role = _determine_role()
    logger.info("Launcher role: %s", role)

    if role == "master":
        return _run_master_mode(port_plan)
    if role == "worker":
        return _run_worker_mode(port_plan)

    # ---- standalone 模式 ----
    return _run_standalone_mode(port_plan)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))