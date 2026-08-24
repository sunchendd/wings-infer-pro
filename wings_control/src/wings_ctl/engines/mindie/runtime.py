"""MindIE 控制侧共享文件准备、运行环境与启动计划生成。

双机时，wings-control 保持部署侧 ``/workspace`` 源 ranktable 不变，将共享目标中的
``device_id`` 归一化为每个 Pod 内的 ``0..N-1``，再发布引擎启动脚本。引擎侧脚本
只检查共享目标，然后加载环境、写入 config.json 并启动 daemon。
"""

from __future__ import annotations

import base64
from builtins import open
import json
import logging
import os
import re
import shlex
import time
from typing import List

from wings_ctl.engines.extension import EngineLaunchPlan
from wings_ctl.engines.mindie.common import DEFAULT_MINDIE_WORK_DIR
from wings_ctl.engines.mindie.config_v230 import (
    MindiePlan,
    build_config_overrides,
    build_full_config,
)
from wings_ctl.engines.mindie.dual_node import MindieDualNodePlan
from wings_ctl.engines.mindie.ranktable import normalize_ranktable_device_ids


MINDIE_CONFIG_TARGET_PATH = "/shared-volume/mindie/config.json"
MINDIE_RANKTABLE_WAIT_SECONDS = 180
_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
logger = logging.getLogger(__name__)


def _ranktable_wait_seconds() -> int:
    raw = os.environ.get(
        "WINGS_MINDIE_RANKTABLE_WAIT_SECONDS",
        str(MINDIE_RANKTABLE_WAIT_SECONDS),
    )
    try:
        timeout_seconds = int(raw)
        if timeout_seconds < 0:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"[mindie] invalid WINGS_MINDIE_RANKTABLE_WAIT_SECONDS={raw!r}") from exc
    return timeout_seconds


def prepare_control_ranktable(plan: MindieDualNodePlan) -> None:
    """由 control 校验物理拓扑、生成容器本地卡号并原子安装。"""
    table = plan.ranktable
    source = os.fspath(table.source_path)
    target = os.fspath(table.target_path)
    timeout_seconds = _ranktable_wait_seconds()
    deadline = time.monotonic() + timeout_seconds
    waiting_logged = False

    while True:
        try:
            with open(source, "rb") as stream:
                payload = stream.read()
            break
        except FileNotFoundError as exc:
            if time.monotonic() >= deadline:
                raise ValueError(f"[mindie] timed out after {timeout_seconds}s waiting for ranktable {source}") from exc
            if not waiting_logged:
                logger.info(
                    "[mindie] waiting up to %ss for ranktable: %s",
                    timeout_seconds,
                    source,
                )
                waiting_logged = True
            time.sleep(1)
        except OSError as exc:
            raise ValueError(f"[mindie] cannot read ranktable {source}: {exc}") from exc

    expected_server_count, remainder = divmod(
        plan.global_world_size,
        plan.local_world_size,
    )
    if remainder:
        raise ValueError(
            "[mindie] global world size must be divisible by local world size, got "
            f"global={plan.global_world_size}, local={plan.local_world_size}"
        )
    adapted_payload, validated_device_count = normalize_ranktable_device_ids(
        payload,
        source_label=source,
        expected_server_count=expected_server_count,
        expected_local_device_count=plan.local_world_size,
        expected_node_ips=plan.node_ips,
    )

    target_dir = os.path.dirname(target) or "."
    tmp_path = f"{target}.wings.{os.getpid()}.tmp"
    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(tmp_path, "wb") as stream:
            stream.write(adapted_payload)
        os.chmod(tmp_path, 0o640)
        os.replace(tmp_path, target)
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise ValueError(f"[mindie] cannot install ranktable {target}: {exc}") from exc

    logger.info(
        "[mindie] installed ranktable with %s physical device ID(s) normalized to container-local ordinals: %s",
        validated_device_count,
        target,
    )


def _build_ranktable_target_check_lines(plan: MindieDualNodePlan) -> List[str]:
    """引擎侧只验证 control 已准备的共享目标，不再访问 control 的 /workspace。"""
    target = str(plan.ranktable.target_path)
    quoted_target = shlex.quote(target)
    error_message = shlex.quote(
        f"[mindie] ERROR: prepared ranktable not readable: {target}; wings-control must install it before engine start"
    )
    return [
        "# MindIE dual-node ranktable prepared by wings-control",
        f"if [ ! -r {quoted_target} ]; then",
        f"    echo {error_message} >&2",
        "    exit 1",
        "fi",
        "",
    ]


def _build_distributed_env_lines(plan: MindieDualNodePlan) -> List[str]:
    """导出标准 Server 动态值；设备 rank 只允许 daemon 从 ranktable 派生。"""
    table = plan.ranktable
    return [
        "# 普通 MindIE Server 在一个 daemon 内管理多个设备进程；节点序号不是设备 RANK。",
        "# 清除 Pod/旧脚本遗留的进程级拓扑，避免全局 rank 被当成本地 ACL device ID。",
        "unset MASTER_ADDR MASTER_PORT RANK LOCAL_RANK WORLD_SIZE NPU_DEVICE_IDS MINDIE_MODEL_WORLD_SIZE",
        # 不解析 ranktable 获取 device_ip。部署可显式提供 HCCL_IF_IP；未提供时使用
        # 当前节点 IP，真正的设备拓扑仍由 MindIE/HCCL 从固定 ranktable 读取。
        f'export HCCL_IF_IP="${{HCCL_IF_IP:-{plan.local_ip}}}"',
        'export HCCL_SOCKET_IFNAME="${HCCL_SOCKET_IFNAME:-eth0}"',
        'export GLOO_SOCKET_IFNAME="${GLOO_SOCKET_IFNAME:-eth0}"',
        f"export MIES_CONTAINER_IP={plan.local_ip}",
        f"export RANK_TABLE_FILE={table.target_path}",
        'export HCCL_WHITELIST_DISABLE="${HCCL_WHITELIST_DISABLE:-1}"',
        'export HCCL_HOST_SOCKET_PORT_RANGE="${HCCL_HOST_SOCKET_PORT_RANGE:-auto}"',
        'export HCCL_NPU_SOCKET_PORT_RANGE="${HCCL_NPU_SOCKET_PORT_RANGE:-auto}"',
        "",
    ]


def _build_static_env_lines(plan: MindiePlan) -> List[str]:
    """在厂商 set_env 后重新导出 Resolver 已合并的 YAML 环境变量。"""
    if not plan.common.static_env:
        return []
    lines = ["# ─── MindIE static environment from resolved YAML ───"]
    for key, value in plan.common.static_env:
        if not _ENV_NAME_PATTERN.fullmatch(key):
            raise ValueError(f"Invalid MindIE environment variable name: {key!r}")
        lines.append(f"export {key}={shlex.quote(str(value))}")
    lines.append("")
    return lines


def _build_runtime_config_lines(plan: MindiePlan, full_config: dict) -> List[str]:
    """生成环境初始化与项目完整 config.json 原子落盘脚本。"""
    payload = json.dumps(full_config, ensure_ascii=False, separators=(",", ":"))
    payload_b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    lines: List[str] = []
    if isinstance(plan, MindieDualNodePlan):
        lines.extend(_build_ranktable_target_check_lines(plan))
    setup_lines = [
        "# ─── MindIE 2.3.0 runtime setup ───",
        f'export MINDIE_WORK_DIR="${{MINDIE_WORK_DIR:-{DEFAULT_MINDIE_WORK_DIR}}}"',
        "# 厂商 set_env.sh 可能读取未定义变量；仅在 source 阶段暂时关闭 nounset。",
        "set +u",
        "wings_require_source() {",
        '    if [ ! -f "$1" ]; then',
        '        echo "[mindie] ERROR: required environment script not found: $1" >&2',
        "        exit 1",
        "    fi",
        '    source "$1"',
        "}",
        "wings_require_source /usr/local/Ascend/ascend-toolkit/set_env.sh",
        "wings_require_source /usr/local/Ascend/nnal/atb/set_env.sh",
        "# MindIE set_env.sh 需要 backend 参数，不能复用上面的单参数 helper。",
        "if [ ! -f /usr/local/Ascend/mindie/set_env.sh ]; then",
        '    echo "[mindie] ERROR: required environment script not found: /usr/local/Ascend/mindie/set_env.sh" >&2',
        "    exit 1",
        "fi",
        "source /usr/local/Ascend/mindie/set_env.sh --backend=atb",
        "# atb-models 只增强部分模型运行环境，不作为最小 daemon 启动的硬依赖。",
        "if [ -f /opt/atb-models/set_env.sh ]; then",
        "    source /opt/atb-models/set_env.sh",
        "else",
        '    echo "[mindie] WARN: optional /opt/atb-models/set_env.sh not found" >&2',
        "fi",
        "set -u",
    ]
    # ScriptBuilder 已在 pre-start 之前导出 env，但厂商脚本可能覆盖这些值；这里使用
    # 同一份 resolved trace 再导出一次，确保 YAML 是静态运行参数的最终来源。
    setup_lines.extend(_build_static_env_lines(plan))
    if isinstance(plan, MindieDualNodePlan):
        # 厂商 set_env 可能设置通用 HCCL 默认值，因此动态拓扑必须在所有 source 完成
        # 后再导出。这样最终环境以已校验计划为准，且两个节点不会被镜像默认值分叉。
        setup_lines.extend(_build_distributed_env_lines(plan))
    setup_lines.extend(
        [
            "# 用户内存参数最终覆盖平台 YAML 缺省，并在厂商 source 后保持生效。",
            f"export NPU_MEMORY_FRACTION={plan.common.npu_memory_fraction:g}",
            f"export MIES_CONFIG_JSON_PATH={MINDIE_CONFIG_TARGET_PATH}",
            f"export _WINGS_MINDIE_CONFIG_TARGET={MINDIE_CONFIG_TARGET_PATH}",
            f"export _WINGS_MINDIE_CONFIG_B64={payload_b64}",
            "python3 << 'WINGS_MINDIE_CONFIG_EOF'",
            "import base64",
            "import json",
            "import os",
            "import sys",
            "",
            "config_path = os.environ['_WINGS_MINDIE_CONFIG_TARGET']",
            "try:",
            "    config = json.loads(base64.b64decode(os.environ['_WINGS_MINDIE_CONFIG_B64']))",
            "except Exception as exc:",
            "    print(f'[mindie] ERROR: invalid generated config payload: {exc}', file=sys.stderr)",
            "    raise SystemExit(1)",
            "",
            "config_dir = os.path.dirname(config_path)",
            "os.makedirs(config_dir, exist_ok=True)",
            "tmp_path = f'{config_path}.wings.{os.getpid()}.tmp'",
            "try:",
            "    with open(tmp_path, 'w', encoding='utf-8') as stream:",
            "        json.dump(config, stream, indent=2, ensure_ascii=False)",
            "        stream.write('\\n')",
            "    os.chmod(tmp_path, 0o640)",
            "    os.replace(tmp_path, config_path)",
            "except OSError as exc:",
            "    try:",
            "        os.unlink(tmp_path)",
            "    except OSError:",
            "        pass",
            "    print(f'[mindie] ERROR: cannot install config {config_path}: {exc}', file=sys.stderr)",
            "    raise SystemExit(1)",
            "print(f'[mindie] external config installed: {config_path}')",
            "WINGS_MINDIE_CONFIG_EOF",
            'cd "$MINDIE_WORK_DIR"',
            "",
        ]
    )
    lines.extend(setup_lines)
    return lines


def build_launch_plan(plan: MindiePlan) -> EngineLaunchPlan:
    """把领域计划转换为公共启动计划，不在此阶段执行任何副作用。"""
    overrides = build_config_overrides(plan)
    full_config = build_full_config(plan)
    preview = "\n".join(
        [
            f"# MindIE external config: {MINDIE_CONFIG_TARGET_PATH}",
            "# MindIE config overrides: " + json.dumps(overrides, ensure_ascii=False, separators=(",", ":")),
            'cd "${MINDIE_WORK_DIR:-' + DEFAULT_MINDIE_WORK_DIR + '}" && ./bin/mindieservice_daemon',
        ]
    )
    return EngineLaunchPlan(
        argv=["./bin/mindieservice_daemon"],
        pre_start_lines=_build_runtime_config_lines(plan, full_config),
        preview=preview,
        preview_label="launch",
        preview_on_new_line=True,
    )
