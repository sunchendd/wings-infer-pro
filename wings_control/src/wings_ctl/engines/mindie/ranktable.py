"""MindIE 双机固定 ranktable 的容器本地设备编号契约。

部署系统把 ``/workspace/rank_table_all.json`` 注入 wings-control，其中
``device_id`` 是宿主机物理卡号。普通 MindIE Server 2.3 的 ``server_list`` schema
只消费 ``device_id``，不会使用 Motor/PD global-ranktable 的
``device_logical_id``。Control 因此保持源文件不变，并在共享目标中按每个 server 的
原始设备顺序把 ``device_id`` 归一化为容器可见序号 ``0..N-1``。

归一化前会校验固定双机规模、每节点设备数、物理卡号唯一性以及全局 rank 分块，
防止把错误拓扑包装成看似可用的目标。``device_ip``、``rank_id`` 和列表顺序均原样
保留；源文件缺失、内容不一致或安装失败时，Control 不发布启动脚本。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from ipaddress import IPv4Address
from pathlib import PurePath, PurePosixPath
from typing import Any


# 源路径属于 Linux control 容器，目标路径属于 control/engine 共同挂载的共享卷。
# 使用 PurePosixPath 可防止在 Windows 上生成/审阅脚本时被改写成反斜杠；测试仍可
# 通过传入本机 Path 替换它们，以验证 control 侧校验和原子安装。
RANKTABLE_SOURCE_PATH = PurePosixPath("/workspace/rank_table_all.json")
RANKTABLE_TARGET_PATH = PurePosixPath("/shared-volume/hccl_ranktable.json")


@dataclass(frozen=True)
class RankTablePlan:
    """部署侧固定源路径和引擎侧固定目标路径。"""

    source_path: PurePath
    target_path: PurePath


def _non_negative_decimal(value: object) -> int | None:
    """把非负十进制整数转为 ``int``；布尔值不属于设备或 rank ID。"""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def _required_ipv4(value: object, *, label: str, source_label: str) -> str:
    """校验 ranktable 中参与节点或 HCCL 映射的 IPv4 字段。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"[mindie] invalid ranktable in {source_label}: {label} must be a valid IPv4 address, got {value!r}"
        )
    try:
        return str(IPv4Address(value.strip()))
    except ValueError as exc:
        raise ValueError(
            f"[mindie] invalid ranktable in {source_label}: {label} must be a valid IPv4 address, got {value!r}"
        ) from exc


def normalize_ranktable_device_ids(
    payload: bytes,
    *,
    source_label: str,
    expected_server_count: int,
    expected_local_device_count: int,
    expected_node_ips: tuple[str, ...] | None = None,
) -> tuple[bytes, int]:
    """生成普通 MindIE Server 使用的容器本地 ranktable。

    源 ``device_id`` 只用于校验每个 server 的物理设备集合；共享目标直接使用
    ``0..N-1``，并删除可能由旧实现写入的 ``device_logical_id``。设备顺序是物理卡
    到容器可见卡的唯一映射契约，因此本函数绝不排序。
    """
    if expected_server_count <= 0 or expected_local_device_count <= 0:
        raise ValueError(
            "[mindie] expected ranktable dimensions must be positive, got "
            f"servers={expected_server_count}, "
            f"local_devices={expected_local_device_count}"
        )
    try:
        document: Any = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"[mindie] invalid ranktable JSON in {source_label}: {exc}") from exc

    if not isinstance(document, dict):
        raise ValueError(f"[mindie] invalid ranktable in {source_label}: root must be an object")
    declared_server_count = _non_negative_decimal(document.get("server_count"))
    if declared_server_count is None:
        raise ValueError(
            f"[mindie] invalid ranktable in {source_label}: server_count must be a non-negative decimal integer"
        )

    servers = document.get("server_list")
    if not isinstance(servers, list) or not servers:
        raise ValueError(f"[mindie] invalid ranktable in {source_label}: server_list must be a non-empty list")

    if declared_server_count != len(servers):
        raise ValueError(
            f"[mindie] invalid ranktable in {source_label}: server_count="
            f"{declared_server_count} does not match server_list size {len(servers)}"
        )
    if len(servers) != expected_server_count:
        raise ValueError(
            f"[mindie] ranktable topology mismatch in {source_label}: expected "
            f"{expected_server_count} servers, got {len(servers)}"
        )

    normalized_expected_node_ips: tuple[str, ...] | None = None
    if expected_node_ips is not None:
        if len(expected_node_ips) != expected_server_count:
            raise ValueError(
                "[mindie] expected node IP count must match expected server count, "
                f"got node_ips={len(expected_node_ips)}, servers={expected_server_count}"
            )
        normalized_expected_node_ips = tuple(
            _required_ipv4(
                value,
                label=f"expected_node_ips[{index}]",
                source_label=source_label,
            )
            for index, value in enumerate(expected_node_ips)
        )
        if len(set(normalized_expected_node_ips)) != len(normalized_expected_node_ips):
            raise ValueError(f"[mindie] expected node IPs must be unique: {normalized_expected_node_ips!r}")

    device_count = 0
    all_rank_ids: list[int] = []
    server_ids: set[str] = set()
    runtime_node_ips: set[str] = set()
    all_device_ips: set[str] = set()
    for server_index, server in enumerate(servers):
        if not isinstance(server, dict):
            raise ValueError(
                f"[mindie] invalid ranktable in {source_label}: server_list[{server_index}] must be an object"
            )

        server_id = _required_ipv4(
            server.get("server_id"),
            label=f"server_list[{server_index}].server_id",
            source_label=source_label,
        )
        if server_id in server_ids:
            raise ValueError(f"[mindie] invalid ranktable in {source_label}: duplicate server_id {server_id}")
        server_ids.add(server_id)

        container_ip_raw = server.get("container_ip")
        runtime_node_ip = server_id
        if container_ip_raw is not None:
            runtime_node_ip = _required_ipv4(
                container_ip_raw,
                label=f"server_list[{server_index}].container_ip",
                source_label=source_label,
            )
        if runtime_node_ip in runtime_node_ips:
            raise ValueError(
                f"[mindie] invalid ranktable in {source_label}: duplicate runtime node IP {runtime_node_ip}"
            )
        runtime_node_ips.add(runtime_node_ip)
        if normalized_expected_node_ips is not None and runtime_node_ip != normalized_expected_node_ips[server_index]:
            raise ValueError(
                f"[mindie] ranktable server identity mismatch in {source_label}: "
                f"server_list[{server_index}] expected runtime IP "
                f"{normalized_expected_node_ips[server_index]}, got {runtime_node_ip}"
            )

        devices = server.get("device")
        if not isinstance(devices, list) or not devices:
            raise ValueError(
                f"[mindie] invalid ranktable in {source_label}: "
                f"server_list[{server_index}].device must be a non-empty list"
            )
        if len(devices) != expected_local_device_count:
            raise ValueError(
                f"[mindie] ranktable topology mismatch in {source_label}: "
                f"server_list[{server_index}] expected "
                f"{expected_local_device_count} devices, got {len(devices)}"
            )

        physical_device_ids: set[int] = set()
        server_rank_ids: list[int] = []
        for local_ordinal, device in enumerate(devices):
            if not isinstance(device, dict):
                raise ValueError(
                    f"[mindie] invalid ranktable in {source_label}: "
                    f"server_list[{server_index}].device[{local_ordinal}] "
                    "must be an object"
                )
            device_ip = _required_ipv4(
                device.get("device_ip"),
                label=(f"server_list[{server_index}].device[{local_ordinal}].device_ip"),
                source_label=source_label,
            )
            if device_ip in all_device_ips:
                raise ValueError(f"[mindie] invalid ranktable in {source_label}: duplicate device_ip {device_ip}")
            all_device_ips.add(device_ip)
            if "device_id" not in device:
                raise ValueError(
                    f"[mindie] invalid ranktable in {source_label}: "
                    f"server_list[{server_index}].device[{local_ordinal}] "
                    "must contain physical device_id"
                )
            device_id = device["device_id"]
            physical_device_id = _non_negative_decimal(device_id)
            if physical_device_id is None:
                raise ValueError(
                    f"[mindie] invalid ranktable in {source_label}: "
                    f"server_list[{server_index}].device[{local_ordinal}].device_id "
                    f"must be a non-negative physical device ID, got {device_id!r}"
                )
            if physical_device_id in physical_device_ids:
                raise ValueError(
                    f"[mindie] invalid ranktable in {source_label}: "
                    f"server_list[{server_index}] contains duplicate physical "
                    f"device_id {physical_device_id}"
                )
            physical_device_ids.add(physical_device_id)

            rank_id = _non_negative_decimal(device.get("rank_id"))
            if rank_id is None:
                raise ValueError(
                    f"[mindie] invalid ranktable in {source_label}: "
                    f"server_list[{server_index}].device[{local_ordinal}].rank_id "
                    "must be a non-negative decimal integer"
                )
            server_rank_ids.append(rank_id)
            all_rank_ids.append(rank_id)

            device["device_id"] = str(local_ordinal)
            device.pop("device_logical_id", None)
            device_count += 1

        first_rank = server_index * expected_local_device_count
        expected_server_ranks = list(range(first_rank, first_rank + expected_local_device_count))
        if server_rank_ids != expected_server_ranks:
            raise ValueError(
                f"[mindie] ranktable rank mapping mismatch in {source_label}: "
                f"server_list[{server_index}] expected rank_id sequence "
                f"{expected_server_ranks}, got {server_rank_ids}"
            )

    expected_rank_ids = list(range(expected_server_count * expected_local_device_count))
    if sorted(all_rank_ids) != expected_rank_ids:
        raise ValueError(
            f"[mindie] ranktable rank mapping mismatch in {source_label}: "
            f"expected global rank IDs {expected_rank_ids}, got {sorted(all_rank_ids)}"
        )

    adapted_payload = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return adapted_payload, device_count


def resolve_ranktable_paths(
    *,
    source_path: PurePath | None = None,
    target_path: PurePath | None = None,
) -> RankTablePlan:
    """返回固定路径计划，不读取或修改文件。

    可选参数只供测试替换生产路径；生产请求没有用户 ranktable path 参数。
    """
    return RankTablePlan(
        source_path=source_path or RANKTABLE_SOURCE_PATH,
        target_path=target_path or RANKTABLE_TARGET_PATH,
    )
