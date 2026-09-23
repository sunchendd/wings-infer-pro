"""AIPerf License gate.

License 校验只做启动门禁,不进入 audit.json:结果结构 ``LicenseRecord``
内聚在本模块,ResolvedConfig 不携带 License 字段。失败时输出一行结构化
``[AIPERF-LICENSE]`` 日志并抛 ``LicenseError``(携带稳定数字错误码)。
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

from wings_ctl.core.models import PipelineRequest, ResolvedConfig

logger = logging.getLogger("wings-license")

DEFAULT_LICENSE_DIR = Path("/etc/aiperf/license")
DEFAULT_STATE_DIR = Path("/var/lib/aiperf/license/adaptivelm")
STATE_FILE_NAME = "adaptivelm.state"
DEFAULT_CHECKER = Path("/opt/wings-license/bin/wings-license-check")
CHECKER_TIMEOUT_SECONDS = 30
DOCKER_SOCKET = Path("/var/run/docker.sock")
EXPECTED_PRODUCT_NAME = "KunLun AIPerf SDK"
EXPECTED_PRODUCT_VERSION = "26"
DEVICE_CAPACITY_KEY = "LRA4AIPERF01"
CHECKER_EXIT_STATUS = {
    2: "checker_error",
    3: "esn_unavailable",
    4: "runtime_error",
    5: "runtime_error",
    6: "invalid",
    7: "product_mismatch",
    8: "node_mismatch",
    9: "capacity_key_invalid",
    10: "expired",
    11: "clock_rolled_back",
    12: "not_yet_valid",
    15: "capacity_exceeded",
}

LICENSE_STATUS_CODES = {
    "missing": 2001,
    "multiple_licenses": 2002,
    "invalid": 2003,
    "not_yet_valid": 2004,
    "expired": 2005,
    "clock_rolled_back": 2006,
    "esn_unavailable": 2007,
    "product_mismatch": 2008,
    "node_mismatch": 2009,
    "capacity_key_invalid": 2010,
    "checker_unavailable": 2011,
    "checker_timeout": 2012,
    "checker_error": 2013,
    "runtime_error": 2014,
    "device_count_unknown": 2016,
    "capacity_exceeded": 2017,
}

STATUS_HINTS = {
    "missing": "no license file found; check the /etc/aiperf/license mount",
    "multiple_licenses": "keep exactly one license file in the directory",
    "invalid": "license signature invalid; contact the license issuer",
    "not_yet_valid": "license not active yet; check system time and validity dates",
    "expired": "license expired; renew it with the license issuer",
    "clock_rolled_back": "system clock rollback detected; correct the system time",
    "esn_unavailable": "device serial unavailable; check dmi mount",
    "product_mismatch": "license product does not match this product",
    "node_mismatch": "license is bound to another device serial",
    "capacity_key_invalid": "license lacks a valid device capacity key",
    "checker_unavailable": "license checker missing or not executable; check image integrity",
    "checker_timeout": "license checker timed out; retry",
    "checker_error": "license checker produced unexpected output",
    "runtime_error": "license checker runtime failure",
    "device_count_unknown": "provide a positive device_count (--device-count / DEVICE_COUNT)",
    "capacity_exceeded": "reduce requested devices or obtain a larger license",
}

LICENSE_ALARM_INTERVAL_SECONDS = 8 * 3600
# 状态文件放共享卷,客户无需新增挂载即可查看;HTTP 查询由 health 服务
# (proxy/health_service.py 的 GET /license_status)读该文件提供。
LICENSE_STATUS_FILE = Path("/shared-volume/license_status.json")


class LicenseError(ValueError):
    """License 校验失败,携带稳定数字错误码供调用方与日志检索。"""

    def __init__(self, record: "LicenseRecord") -> None:
        self.code = LICENSE_STATUS_CODES.get(record.status, 2000)
        self.status = record.status
        self.record = record
        hint = record.reason or STATUS_HINTS.get(record.status, "")
        super().__init__(f"{self.code} {record.status}: {hint}")


@dataclass(frozen=True)
class LicenseRecord:
    """License 门禁结果。

    仅存在于 License 校验流程内部(异常与日志),不写入 audit.json,
    也不挂到 ResolvedConfig —— License 不做审计。
    """

    status: str
    license_id: str | None = None
    product_name: str | None = None
    product_version: str | None = None
    capacity_key: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    grace_until: str | None = None
    authorized_device_count: int | None = None
    actual_device_count: int | None = None
    used_device_count: int | None = None
    license_file: str | None = None
    reason: str | None = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LicenseCheckResult:
    allowed: bool
    record: LicenseRecord


class AmbiguousLicenseError(ValueError):
    pass


def _fail(status: str, reason: str, reason_extra: str | None = None, **extra: Any) -> LicenseCheckResult:
    if reason_extra:
        reason = f"{reason}; {reason_extra}"
    return LicenseCheckResult(False, LicenseRecord(status=status, reason=reason, **extra))


def _try_parse_json(text: str) -> dict | None:
    """尽力解析 checker stdout 的 JSON;失败(空/非 JSON/非对象)返回 None。"""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _opt_int(value: Any) -> int | None:
    """checker JSON 数值字段的保守提取:非 int(含 bool)一律 None。"""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _load_reason(payload: dict | None) -> str | None:
    if payload and isinstance(payload.get("reason"), str) and payload["reason"]:
        return payload["reason"]
    return None


_ENGINE_SERVICE_LABEL = "com.docker.compose.service=aiperf-engine"
_DEVICE_ENV_KEYS = (
    "ASCEND_RT_VISIBLE_DEVICES",
    "ASCEND_VISIBLE_DEVICES",
    "NVIDIA_VISIBLE_DEVICES",
)


def _http_get_over_unix_socket(socket_path: Path, path: str) -> Any:
    """经 unix socket 执行一次 Docker API GET;socket 由 with 保证所有路径必关。"""
    import http.client
    import socket as socket_mod

    connection = http.client.HTTPConnection("localhost")
    with socket_mod.socket(socket_mod.AF_UNIX, socket_mod.SOCK_STREAM) as sock:
        sock.settimeout(10)
        connection.sock = sock
        # with 块退出(含 connect/request 异常)时 socket.close() 必被调用,
        # 满足资源申请/释放成对;connection 无底层资源,无需再 close。
        sock.connect(str(socket_path))
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
    if response.status != 200:
        raise RuntimeError("docker api %s on %s" % (response.status, path))
    return json.loads(body)


def _parse_device_spec(spec: str) -> int | None:
    """解析 VISIBLE_DEVICES 值为卡数;"all" 返回 None 表示该来源无法计数。

    "all" 意味着容器可见全部物理卡,数量必须从容器设备配置(DeviceRequests/
    直通设备)获取——若按 0 计,多实例部署可用 env 规避配额。
    """
    total = 0
    for token in str(spec or "").split(","):
        token = token.strip()
        if token in ("all",):
            return None
        if token in ("", "void", "none"):
            continue
        low, sep, high = token.partition("-")
        if sep and low.strip().isdigit() and high.strip().isdigit():
            total += int(high) - int(low) + 1
        else:
            total += 1
    return total


def count_devices_from_env(env_list: Any) -> int | None:
    """从容器 env 提取可见卡数;"all"/缺失返回 None(交由设备配置回退计数)。"""
    for item in env_list or []:
        key, _, value = str(item).partition("=")
        if key in _DEVICE_ENV_KEYS:
            return _parse_device_spec(value)
    return None


def _count_container_devices(info: dict) -> int:
    host_config = info.get("HostConfig") or {}
    from_env = count_devices_from_env((info.get("Config") or {}).get("Env"))
    if from_env is not None:
        return from_env
    davinci = sum(
        1
        for device in host_config.get("Devices") or []
        if str(device.get("PathInContainer", "")).startswith("/dev/davinci")
    )
    if davinci:
        return davinci
    total = 0
    for request in host_config.get("DeviceRequests") or []:
        ids = request.get("DeviceIDs") or []
        total += len(ids) if ids else (request.get("Count") or 0)
    return total


_COMPOSE_PROJECT_LABEL = "com.docker.compose.project"

# cgroup v1: "…:/docker/<64hex>";cgroup v2(共享 cgroupns):"0::/…/docker-<64hex>.scope"。
_CGROUP_CONTAINER_ID = re.compile(r"docker[-/]([0-9a-f]{64})(?:\.scope)?")
# Docker 把 /etc/hosts、/etc/hostname、/etc/resolv.conf 从数据目录
# (默认 /var/lib/docker,可迁移)bind 进容器,mountinfo 行内含 containers/<id>/。
_MOUNTINFO_CONTAINER_ID = re.compile(r"/containers/([0-9a-f]{64})/(?:hosts|hostname|resolv\.conf)")
# 默认桥接网络下 Docker 注入的 HOSTNAME 为容器短 ID(12+ 位 hex);
# host 网络等场景 HOSTNAME 继承宿主机名(非 hex),不能作容器 ID 用。
_HOSTNAME_AS_ID = re.compile(r"^[0-9a-f]{12,64}$")
_SELF_CGROUP_PATH = Path("/proc/self/cgroup")
_SELF_MOUNTINFO_PATH = Path("/proc/self/mountinfo")


def self_container_id(cgroup_text: str | None = None, mountinfo_text: str | None = None) -> str | None:
    """解析自身容器 ID(Docker 运行时),识别链三层逐级回退。

    HOSTNAME 不能作为依据:host 网络模式下容器继承宿主机名(如 cp0),
    拿它查 Docker API 必 404,自识别恒失败会退化为全量计数。识别链:
    /proc/self/cgroup(v1 ``docker/<id>``、v2 共享 cgroupns 的
    ``docker-<id>.scope``)→ /proc/self/mountinfo(Docker bind 的 hosts/
    hostname/resolv.conf 源路径含 containers/<id>/,不随 cgroup 版本与
    namespace 模式变化)→ HOSTNAME 为 12-64 位 hex(默认桥接网络的注入
    形态)。非容器环境或均无法解析返回 None,调用方保守不剔除任何人。

    入参用于测试注入;缺省时读现场 /proc 文件。
    """

    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    if cgroup_text is None:
        cgroup_text = _read(_SELF_CGROUP_PATH)
    if mountinfo_text is None:
        mountinfo_text = _read(_SELF_MOUNTINFO_PATH)
    for match in _CGROUP_CONTAINER_ID.finditer(cgroup_text):
        return match.group(1)
    match = _MOUNTINFO_CONTAINER_ID.search(mountinfo_text)
    if match:
        return match.group(1)
    hostname = os.environ.get("HOSTNAME", "")
    if hostname and _HOSTNAME_AS_ID.match(hostname):
        return hostname
    return None


def _self_compose_project(socket_path: Path) -> str | None:
    """查询自身容器所属的 compose project label。

    本门禁运行在 aiperf-control 容器内;同 project 的 aiperf-engine 正在
    等待本次授权产出的 start_command.sh,其卡数已由 request_devices 表达,
    计数时必须剔除,否则等待中的 engine 会被重复计入 used 导致恒超容。
    识别不出(非容器环境/非 compose 部署/API 异常)返回 None,调用方此时
    不剔除任何人——多计方向保守,不会放过配额。
    """
    container_id = self_container_id()
    if not container_id:
        return None
    try:
        info = _http_get_over_unix_socket(socket_path, "/containers/{0}/json".format(container_id))
        labels = (info.get("Config") or {}).get("Labels") or {}
        project = labels.get(_COMPOSE_PROJECT_LABEL)
        return str(project) if project else None
    except Exception as exc:
        logger.debug("[AIPERF-LICENSE] self project detection unavailable: %s", exc)
        return None


def count_used_devices(socket_path: Path | None = None) -> int | None:
    """Count devices held by running engine containers via the Docker API.

    Engine containers from the caller's own compose project are excluded:
    that instance is the one waiting for this authorization (its devices are
    the request_devices term), so counting it would double-count every
    first-time deployment. Returns None when the daemon is unreachable
    (standalone deployments without the socket mount degrade to a
    per-instance check).
    """
    from urllib.parse import urlencode

    socket_path = socket_path or DOCKER_SOCKET
    if not socket_path.exists():
        return None
    try:
        filters = urlencode({"filters": json.dumps({"label": [_ENGINE_SERVICE_LABEL]})})
        # 注意:此处拼接的是 HTTP API 的 query string,不是文件系统路径。
        containers = _http_get_over_unix_socket(socket_path, "/containers/json?{0}".format(filters))
        self_project = _self_compose_project(socket_path)
        total = 0
        for item in containers:
            labels = item.get("Labels") or {}
            if self_project and labels.get(_COMPOSE_PROJECT_LABEL) == self_project:
                continue
            total += _count_container_devices(
                _http_get_over_unix_socket(socket_path, "/containers/{0}/json".format(item["Id"]))
            )
        return total
    except Exception as exc:
        logger.warning("[AIPERF-LICENSE] quota detection degraded to zero: %s", exc)
        return None


def resolve_unique_license(license_dir: Path | None = None) -> Path:
    license_dir = license_dir or DEFAULT_LICENSE_DIR
    candidates = sorted(license_dir.glob("*.xml")) if license_dir.is_dir() else []
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise AmbiguousLicenseError(
            f"multiple license files in {license_dir}: {names}; exactly one is allowed"
        )
    if not candidates:
        raise FileNotFoundError(f"no license file (*.xml) in {license_dir}")
    return candidates[0]


def _resolve_license_path(license_target: Path | None) -> Path:
    """目录(含默认目录)→ 其内唯一证书;显式文件 → 原样返回。"""
    if license_target is None or license_target.is_dir():
        return resolve_unique_license(license_target)
    return license_target


def _parse_checker_output(payload: Any, license_file: str | None = None) -> LicenseCheckResult:
    if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
        raise ValueError("checker output must contain string field 'status'")
    if payload.get("product_name") != EXPECTED_PRODUCT_NAME:
        raise ValueError(f"unexpected License product: {payload.get('product_name')!r}")
    if str(payload.get("product_version")) != EXPECTED_PRODUCT_VERSION:
        raise ValueError(f"unexpected License product version: {payload.get('product_version')!r}")
    if payload.get("capacity_key") != DEVICE_CAPACITY_KEY:
        raise ValueError(f"required capacity key is missing: {DEVICE_CAPACITY_KEY}")
    authorized = payload.get("authorized_device_count")
    if not isinstance(authorized, int) or isinstance(authorized, bool) or authorized < 0:
        raise ValueError("checker output has invalid 'authorized_device_count'")
    status = payload["status"]
    return LicenseCheckResult(
        # 过期(宽限期结束)按告警放行,由告警守护周期提示并开放状态查询。
        status in {"valid", "grace", "expired"},
        LicenseRecord(
            status=status,
            license_id=payload.get("license_id"),
            product_name=payload.get("product_name"),
            product_version=str(payload.get("product_version")),
            capacity_key=payload.get("capacity_key"),
            valid_from=payload.get("valid_from"),
            valid_until=payload.get("valid_until"),
            grace_until=payload.get("grace_until"),
            authorized_device_count=authorized,
            license_file=license_file,
            reason=payload.get("reason"),
        ),
    )


def check_license(
    license_target: Path | None = None,
    state_dir: Path = DEFAULT_STATE_DIR,
    used_devices: int | None = None,
    request_devices: int | None = None,
) -> LicenseCheckResult:
    """Locate the unique license and run the native checker; fail closed."""
    try:
        path = _resolve_license_path(license_target)
    except AmbiguousLicenseError as exc:
        return _fail("multiple_licenses", str(exc))
    except FileNotFoundError as exc:
        return _fail("missing", str(exc))
    if not path.is_file():
        return _fail("missing", f"License file does not exist: {path}", license_file=str(path))
    if not DEFAULT_CHECKER.is_file():
        return _fail(
            "checker_unavailable",
            f"AdaptiveLM checker does not exist: {DEFAULT_CHECKER}",
            license_file=str(path),
        )

    argv = [str(DEFAULT_CHECKER), "--license-file", str(path), "--state-dir", str(state_dir)]
    if used_devices is not None and request_devices is not None:
        argv += ["--used-devices", str(used_devices), "--request-devices", str(request_devices)]
    if not (state_dir / STATE_FILE_NAME).is_file():
        argv.append("--initialize-state")
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=CHECKER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return _fail(
            "checker_timeout",
            f"AdaptiveLM checker exceeded {CHECKER_TIMEOUT_SECONDS}s timeout",
            license_file=str(path),
        )
    except OSError as exc:
        return _fail("checker_unavailable", f"Failed to execute AdaptiveLM checker: {exc}", license_file=str(path))
    if completed.returncode != 0:
        status = CHECKER_EXIT_STATUS.get(completed.returncode, "runtime_error")
        # checker 非零退出时 stdout 可能仍携带结构化数字(如 capacity_exceeded 的
        # authorized/used/requested);能解析就并入记录,让日志可直接回答"该减到几卡"。
        payload = _try_parse_json(completed.stdout)
        if status == "expired" and payload is not None:
            # 过期路径(exit 10)携带完整结构化结果;能解析成合法 expired 记录
            # 就按告警放行,解析失败保持 fail-closed,不放宽畸形输出。
            try:
                return _parse_checker_output(payload, license_file=str(path))
            except ValueError:
                pass
        return _fail(
            status,
            completed.stderr.strip() or f"checker exited with {completed.returncode}",
            license_file=str(path),
            license_id=payload.get("license_id") if payload else None,
            authorized_device_count=_opt_int(payload.get("authorized_device_count")) if payload else None,
            used_device_count=_opt_int(payload.get("used_device_count")) if payload else None,
            reason_extra=_load_reason(payload),
        )
    try:
        return _parse_checker_output(json.loads(completed.stdout), license_file=str(path))
    except ValueError as exc:  # JSONDecodeError 是 ValueError 子类,单捕父类即可
        return _fail("checker_error", str(exc), license_file=str(path))


def format_license_log(record: LicenseRecord) -> str:
    """把门禁结果格式化为一行结构化日志字段(不含前缀)。

    成功与失败共用同一字段序列,按 code/status 可直接 grep;空值字段
    不输出,避免噪音。
    """
    parts = [
        f"code={LICENSE_STATUS_CODES.get(record.status, 2000)}",
        f"status={record.status}",
    ]
    for key, value in (
        ("license_id", record.license_id),
        ("license_file", record.license_file),
        ("authorized", record.authorized_device_count),
        ("used", record.used_device_count),
        ("requested", record.actual_device_count),
        ("reason", record.reason),
    ):
        if value is not None:
            parts.append(f"{key}={value}")
    parts.append(f"hint={STATUS_HINTS.get(record.status, '')}")
    return " ".join(parts)


def fail_device_count_unknown(device_count: Any) -> LicenseCheckResult:
    """构造 ``device_count_unknown``(2016)失败结果;校验入口与 enforce 共用。"""
    return _fail(
        "device_count_unknown",
        f"license quota requires a positive device_count (--device-count / DEVICE_COUNT), got {device_count!r}",
    )


def is_positive_int(value: Any) -> bool:
    """License 配额语义下的合法卡数:int 且非 bool 且 > 0。"""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_device_count(device_count: Any) -> LicenseCheckResult:
    """校验 device_count 为正整数;缺失/非正整数 → 2016 device_count_unknown。

    设计 §6「device_count 必填,缺失或不是正整数直接拒绝启动」的唯一校验
    入口:CLI 前移校验(先于 TP-shrink 等 device_count 依赖逻辑)与 enforce
    内部兜底共用,保证错误码与日志行形态一致。失败时输出与 enforce 相同
    的结构化日志行。
    """
    if is_positive_int(device_count):
        return LicenseCheckResult(True, LicenseRecord(status="valid"))
    result = fail_device_count_unknown(device_count)
    logger.error(
        "[AIPERF-LICENSE] %s",
        format_license_log(replace(result.record, actual_device_count=None)),
    )
    return result


class LicensePublisher:
    """Gate before artifacts are published; old start script is removed first."""

    @staticmethod
    def validate_device_count(device_count: object) -> None:
        """CLI 前移强校验:缺失/非正整数 → 2016 日志 + 抛错(先于 TP-shrink)。"""
        result = validate_device_count(device_count)
        if not result.allowed:
            raise LicenseError(result.record)

    @staticmethod
    def enforce(request: PipelineRequest, resolved: ResolvedConfig) -> None:
        # Order: validate device_count first (fail-closed), then count in-use
        # devices via the Docker API (in-image, not injectable via env), then
        # let the native checker compare used+request against the certificate
        # capacity. Checker comparison only runs when the signature is valid.
        cards = request.device_count
        used: int | None = None
        if not is_positive_int(cards):
            result = fail_device_count_unknown(cards)
            cards = None
        else:
            detected = count_used_devices()
            if detected is None:
                used = 0
            else:
                used = detected
            result = check_license(
                request.license_file,
                used_devices=used,
                request_devices=cards,
            )
        record = replace(result.record, actual_device_count=cards, used_device_count=used)
        if not result.allowed:
            logger.error("[AIPERF-LICENSE] %s", format_license_log(record))
            raise LicenseError(record)
        if record.status in ("grace", "expired"):
            # 宽限期=证书已到期、进入倒计时;过期=宽限期已过、仅告警放行
            # (运行与重拉不受限,模型升级等人工服务按商务策略停止)。
            logger.warning("[AIPERF-LICENSE] %s", format_license_log(record))
        else:
            logger.info("[AIPERF-LICENSE] %s", format_license_log(record))
        _spawn_alarm_daemon()

    @staticmethod
    def invalidate(output_dir: Path) -> None:
        try:
            (output_dir / "start_command.sh").unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def artifact_dir(output_dir: Path) -> Tuple[Path, None]:
        return output_dir, None

    @staticmethod
    def lock(output_dir: Path):
        return nullcontext()

    @staticmethod
    def publish(output_dir: Path, generation: None, artifact_dir: Path) -> Path:
        return artifact_dir


# ---------------------------------------------------------------------------
# 过期告警守护:证书过期(宽限期结束)后运行中服务不受影响,由常驻
# 守护每 8 小时复验一次证书,并把最近一次校验结果落盘共享卷状态文件。
# HTTP 查询不独立占端口,由 health 服务读状态文件提供(路径区分路由)。
# 守护进程由 enforce 放行后派生,随 control 容器生命周期存活;
# 仅 License 镜像携带本模块,普通构建天然无此能力。
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """状态查询载荷的时间戳(UTC,秒级 ISO-8601)。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def license_status_payload(record: LicenseRecord, checked_at: str, interval_seconds: int) -> Dict[str, Any]:
    """把一次校验记录转成对外状态查询载荷;字段只增不改,空值不输出。"""
    payload: Dict[str, Any] = {
        "status": record.status,
        "code": LICENSE_STATUS_CODES.get(record.status, 2000),
        "checked_at": checked_at,
        "alarm_interval_seconds": interval_seconds,
        "license_id": record.license_id,
        "valid_until": record.valid_until,
        "grace_until": record.grace_until,
        "authorized_device_count": record.authorized_device_count,
        "reason": record.reason,
        "hint": STATUS_HINTS.get(record.status, ""),
    }
    return {key: value for key, value in payload.items() if value is not None}


def run_alarm_pass(state_dir: Path, interval_seconds: int, status_file: Path = LICENSE_STATUS_FILE) -> LicenseRecord:
    """单轮巡检:复验证书时间有效性,输出告警并刷新状态文件。

    只做时间有效性复验(不传卡数):配额判定属启动门禁职责且不因过期豁免,
    守护只负责告警与状态暴露,不拦截任何服务。非 valid 状态(含 grace/
    expired/checker 异常)一律 warning,让告警通道成为过期后唯一的持续
    感知入口。
    """
    result = check_license(None, state_dir=state_dir)
    record = result.record
    if record.status != "valid":
        logger.warning("[AIPERF-LICENSE] %s", format_license_log(record))
    else:
        logger.info("[AIPERF-LICENSE] %s", format_license_log(record))
    payload = license_status_payload(record, _utc_now_iso(), interval_seconds)
    try:
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("[AIPERF-LICENSE] failed to persist license status file %s: %s", status_file, exc)
    return record


def run_license_alarm(
    interval_seconds: int = LICENSE_ALARM_INTERVAL_SECONDS,
    state_dir: Path = DEFAULT_STATE_DIR,
    status_file: Path = LICENSE_STATUS_FILE,
) -> None:
    """过期告警守护进程主体:立即巡检一次,之后每 8 小时复验并落盘状态文件。

    HTTP 查询不在此进程内:由 health 服务读状态文件提供
    GET /license_status,避免独立占用端口。单轮巡检异常只告警
    不中断周期。函数不返回,进程由容器生命周期管理。
    """
    # 守护子进程未继承 CLI 的日志初始化:补挂 stderr handler,
    # 否则 INFO 级启动/巡检日志被 lastResort 丢弃,只剩 WARNING 可见。
    logging.basicConfig(level=logging.INFO)
    try:
        run_alarm_pass(state_dir, interval_seconds, status_file)
    except Exception as exc:  # 守护进程边界:首轮失败不阻断周期,由后续轮次补
        logger.warning("[AIPERF-LICENSE] alarm check failed: %s", exc)
    logger.info("[AIPERF-LICENSE] alarm daemon started (interval=%ss)", interval_seconds)
    while True:
        time.sleep(interval_seconds)
        try:
            run_alarm_pass(state_dir, interval_seconds, status_file)
        except Exception as exc:  # 守护进程边界:单轮巡检失败不终止周期告警
            logger.warning("[AIPERF-LICENSE] alarm check failed: %s", exc)
            continue


# 守护进程启动代码:显式插入 src 根路径,兼容明文源码树与 .pyc-only 交付镜像。
_ALARM_DAEMON_ENTRY = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from wings_ctl.license import run_license_alarm; run_license_alarm()"
)


def _spawn_alarm_daemon() -> None:
    """派生过期告警守护进程(8 小时周期 + 状态查询接口),尽力而为。

    start_new_session 使守护脱离门禁进程会话,control 容器内随容器存活;
    派生失败只降低过期可观测性,不影响启动门禁结论。
    """
    src_dir = str(Path(__file__).resolve().parent.parent)
    try:
        subprocess.Popen([sys.executable, "-c", _ALARM_DAEMON_ENTRY, src_dir], start_new_session=True)
    except OSError as exc:
        logger.warning("[AIPERF-LICENSE] license alarm daemon failed to start: %s", exc)
