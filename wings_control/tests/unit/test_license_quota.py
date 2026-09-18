"""License 配额单测:容器内自查语义 / checker 参数传递 / 失败路径。

不打 native checker:monkeypatch ``license.count_used_devices`` 与
``license.check_license``,验证 enforce 编排(device_count 校验 → 自查 →
checker 比较)与失败抛错。License 不做审计:结果不挂 ResolvedConfig,
只体现在异常与日志。

普通构建会物理删除 ``wings_ctl.license``(build_wings_control.sh 的
prepare_build_context),该形态下本文件整体跳过——关闭 License 不影响
wings_control 其余测试。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from wings_ctl import license as license_mod
except ImportError:  # 普通构建无门禁模块(子模块缺失在部分路径抛 ImportError 而非 ModuleNotFoundError)
    pytest.skip(
        "wings_ctl.license not present in this build (license disabled)",
        allow_module_level=True,
    )


def _allowed(authorized: int) -> license_mod.LicenseCheckResult:
    return license_mod.LicenseCheckResult(
        True,
        license_mod.LicenseRecord(status="valid", authorized_device_count=authorized),
    )


def _failed(status: str) -> license_mod.LicenseCheckResult:
    return license_mod.LicenseCheckResult(False, license_mod.LicenseRecord(status=status))


def _request(device_count: int | None, license_file: Path | None = None) -> SimpleNamespace:
    return SimpleNamespace(device_count=device_count, license_file=license_file)


def _resolved() -> SimpleNamespace:
    # ResolvedConfig 已无 license 字段;enforce 不应向 resolved 写任何东西。
    return SimpleNamespace()


def test_passes_when_detection_degrades_to_zero(monkeypatch):
    """Docker daemon 不可达(独立部署/无 sock)时按 0,退化为单次校验。"""
    seen = {}
    monkeypatch.setattr(license_mod, "count_used_devices", lambda: None)

    def fake_check(target, used_devices=None, request_devices=None):
        seen.update(used=used_devices, request=request_devices)
        return _allowed(8)

    monkeypatch.setattr(license_mod, "check_license", fake_check)

    license_mod.LicensePublisher().enforce(_request(device_count=8), _resolved())

    assert seen == {"used": 0, "request": 8}


def test_used_and_request_are_passed_to_checker(monkeypatch):
    monkeypatch.setattr(license_mod, "count_used_devices", lambda: 6)
    seen = {}

    def fake_check(target, used_devices=None, request_devices=None):
        seen.update(used=used_devices, request=request_devices)
        return _allowed(8)

    monkeypatch.setattr(license_mod, "check_license", fake_check)

    license_mod.LicensePublisher().enforce(_request(device_count=4), _resolved())

    assert seen == {"used": 6, "request": 4}


def test_capacity_exceeded_comes_from_checker(monkeypatch):
    """超容判定由 native checker 返回(exit 15 → capacity_exceeded)。"""
    monkeypatch.setattr(license_mod, "count_used_devices", lambda: 5)
    monkeypatch.setattr(
        license_mod,
        "check_license",
        lambda target, used_devices=None, request_devices=None: _failed("capacity_exceeded"),
    )

    with pytest.raises(ValueError, match="capacity_exceeded"):
        license_mod.LicensePublisher().enforce(_request(device_count=4), _resolved())


def test_missing_device_count_fails_closed_without_checker(monkeypatch):
    """device_count 缺失直接拒绝,不调自查也不调 checker。"""
    calls = []

    def fail(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("check_license must not run")

    monkeypatch.setattr(license_mod, "count_used_devices", fail)
    monkeypatch.setattr(license_mod, "check_license", fail)

    with pytest.raises(ValueError, match="device_count_unknown"):
        license_mod.LicensePublisher().enforce(_request(device_count=None), _resolved())

    assert not calls


def test_invalid_license_skips_quota(monkeypatch):
    """验签失败时 checker 不做配额比较,直接抛 expired。"""
    monkeypatch.setattr(license_mod, "count_used_devices", lambda: 99)
    monkeypatch.setattr(
        license_mod,
        "check_license",
        lambda target, used_devices=None, request_devices=None: _failed("expired"),
    )

    with pytest.raises(ValueError, match="expired"):
        license_mod.LicensePublisher().enforce(_request(device_count=4), _resolved())


def test_invalid_device_count_type_fails_closed(monkeypatch):
    monkeypatch.setattr(license_mod, "count_used_devices", lambda: 0)
    monkeypatch.setattr(
        license_mod,
        "check_license",
        lambda *a, **k: pytest.fail("check_license must not run"),
    )

    with pytest.raises(ValueError, match="device_count_unknown"):
        license_mod.LicensePublisher().enforce(_request(device_count=0), _resolved())


# ─── 前移校验 validate_device_count(设计 §6:缺失/非正整数 → 2016)───────────


@pytest.mark.parametrize("bad", [None, 0, -1, -8, True, "4", 1.0])
def test_validate_device_count_rejects_missing_or_non_positive(monkeypatch, bad):
    """None/0/负数/bool/非 int → LicenseError code=2016,不触自查与 checker。"""
    monkeypatch.setattr(
        license_mod,
        "count_used_devices",
        lambda *a, **k: pytest.fail("count_used_devices must not run"),
    )
    monkeypatch.setattr(
        license_mod,
        "check_license",
        lambda *a, **k: pytest.fail("check_license must not run"),
    )

    with pytest.raises(license_mod.LicenseError) as excinfo:
        license_mod.LicensePublisher().validate_device_count(bad)

    assert excinfo.value.code == 2016
    assert excinfo.value.status == "device_count_unknown"
    assert "device_count" in str(excinfo.value)


@pytest.mark.parametrize("good", [1, 8, 16])
def test_validate_device_count_accepts_positive_int(monkeypatch, good):
    """正整数直接放行,不触发 docker 自查与 checker(那些归 enforce)。"""
    monkeypatch.setattr(
        license_mod,
        "count_used_devices",
        lambda *a, **k: pytest.fail("count_used_devices must not run"),
    )
    monkeypatch.setattr(
        license_mod,
        "check_license",
        lambda *a, **k: pytest.fail("check_license must not run"),
    )

    license_mod.LicensePublisher().validate_device_count(good)


def test_validate_device_count_logs_structured_2016(caplog):
    """前移校验失败输出与 enforce 同形态的结构化日志行(code=2016)。"""
    import logging

    with caplog.at_level(logging.ERROR, logger="wings-license"):
        license_mod.validate_device_count(None)

    lines = [r.message for r in caplog.records if r.message.startswith("[AIPERF-LICENSE]")]
    assert lines, "structured [AIPERF-LICENSE] log line must be emitted"
    assert lines[0].startswith("[AIPERF-LICENSE] code=2016 status=device_count_unknown")
    assert "hint=" in lines[0]


def test_cli_license_build_rejects_missing_device_count_before_pipeline(
    monkeypatch, caplog, capsys, config_root_real, tmp_path
):
    """License 构建:CLI 前移校验先于解析流水线生效。

    回归:env 未提供 DEVICE_COUNT 且未传 --device-count 时,旧行为把
    device_count=None 放进解析流水线,由 TP-shrink 相关校验抛出误导性的
    hardware_family 报错;现在参数解析后立即以 code=2016 拒绝。
    """
    import json
    import logging

    from wings_ctl import cli, license_gate

    monkeypatch.setattr(cli, "setup_root_logging", lambda: None)
    monkeypatch.setattr(license_gate, "LICENSE_ENABLED", True)
    monkeypatch.delenv("DEVICE_COUNT", raising=False)
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps({"hardware_family": "gb300", "device": "nvidia", "count": 8}))
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--engine",
            "vllm",
            "--config-root",
            str(config_root_real),
            "--hardware-info",
            str(hw),
            "--dry-run",
        ],
    )

    with caplog.at_level(logging.WARNING):
        with pytest.raises(BaseException) as exc:
            cli.main()

    assert exc.value.code == 2
    license_lines = [r.message for r in caplog.records if r.message.startswith("[AIPERF-LICENSE]")]
    assert license_lines and license_lines[0].startswith("[AIPERF-LICENSE] code=2016")
    # 不得再出现把人指向 hardware_family 配置的误导性报错。
    assert not any("hardware_family" in r.message for r in caplog.records)
    err = capsys.readouterr().err
    assert "2016 device_count_unknown" in err


def test_error_carries_stable_numeric_code():
    """LicenseError 的数字码与状态一一对应,供日志/调用方检索。"""
    record = license_mod.LicenseRecord(status="expired", reason="license expired")
    error = license_mod.LicenseError(record)
    assert error.code == 2005
    assert "2005 expired" in str(error)


def test_failure_log_line_is_structured(caplog):
    """失败日志一行结构化:code/status/license_file/used/requested/reason/hint。"""
    record = license_mod.LicenseRecord(
        status="capacity_exceeded",
        license_file="/etc/aiperf/license/a.xml",
        authorized_device_count=6,
        actual_device_count=8,
        used_device_count=1,
        reason="used 1 + requested 8 > authorized 6",
    )
    line = license_mod.format_license_log(record)
    assert line.startswith("code=2017 status=capacity_exceeded")
    assert "license_file=/etc/aiperf/license/a.xml" in line
    assert "authorized=6" in line and "used=1" in line and "requested=8" in line
    assert "reason=used 1 + requested 8 > authorized 6" in line
    assert "hint=" in line


def test_count_used_devices_parses_env_and_range(monkeypatch):
    assert license_mod.count_devices_from_env(["ASCEND_VISIBLE_DEVICES=10,12"]) == 2
    assert license_mod.count_devices_from_env(["NVIDIA_VISIBLE_DEVICES=0-3"]) == 4
    # "all"=全部物理卡,env 来源无法计数 → None,回退设备配置计数(防配额规避)。
    assert license_mod.count_devices_from_env(["NVIDIA_VISIBLE_DEVICES=all"]) is None
    assert license_mod.count_devices_from_env([]) is None


def test_count_used_devices_returns_none_without_socket(monkeypatch, tmp_path):
    assert license_mod.count_used_devices(socket_path=tmp_path / "missing.sock") is None


FULL_ID = "0123456789abcdef" * 4  # 64 位 hex 容器 ID


def test_self_container_id_from_cgroup_v1():
    """cgroup v1 行 …:/docker/<64hex> 命中第一优先级。"""
    text = "12:perf_event:/\n11:cpu,cpuacct:/docker/{0}\n".format(FULL_ID)
    assert license_mod.self_container_id(cgroup_text=text, mountinfo_text="") == FULL_ID


def test_self_container_id_from_cgroup_v2_scope():
    """cgroup v2(共享 cgroupns)行 0::/…/docker-<64hex>.scope 同样命中。"""
    text = "0::/system.slice/docker-{0}.scope\n".format(FULL_ID)
    assert license_mod.self_container_id(cgroup_text=text, mountinfo_text="") == FULL_ID


def test_self_container_id_from_mountinfo_when_cgroup_blank():
    """cgroup 私有 namespace 时 cgroup 为 0::/,回退 mountinfo 的 bind 源路径。"""
    mountinfo = "705 679 8:3 /var/lib/docker/containers/{0}/hosts /etc/hosts rw - ext4 /dev/sda1 rw\n".format(FULL_ID)
    assert license_mod.self_container_id(cgroup_text="0::/\n", mountinfo_text=mountinfo) == FULL_ID


def test_self_container_id_mountinfo_survives_relocated_data_root():
    """Docker data-root 迁移后源路径前缀不同,按 containers/<id>/ 文件名匹配。"""
    mountinfo = "705 679 8:3 /data/docker/containers/{0}/hostname /etc/hostname rw - ext4 /dev/sda1 rw\n".format(
        FULL_ID
    )
    assert license_mod.self_container_id(cgroup_text="", mountinfo_text=mountinfo) == FULL_ID


def test_self_container_id_hostname_hex_fallback():
    """前两层空时,HOSTNAME 为 12-64 位 hex(默认桥接网络)可作短 ID 用。"""
    import os

    old = os.environ.get("HOSTNAME")
    os.environ["HOSTNAME"] = "abc123def456789"
    try:
        got = license_mod.self_container_id(cgroup_text="", mountinfo_text="")
    finally:
        if old is None:
            os.environ.pop("HOSTNAME", None)
        else:
            os.environ["HOSTNAME"] = old
    assert got == "abc123def456789"


def test_self_container_id_hostname_cp0_is_rejected():
    """host 网络继承的宿主机名(cp0)非 hex,不得当容器 ID(实测回归点)。"""
    import os

    old = os.environ.get("HOSTNAME")
    os.environ["HOSTNAME"] = "cp0"
    try:
        got = license_mod.self_container_id(cgroup_text="", mountinfo_text="")
    finally:
        if old is None:
            os.environ.pop("HOSTNAME", None)
        else:
            os.environ["HOSTNAME"] = old
    assert got is None


def _fake_docker_api(monkeypatch, tmp_path, containers, self_info, self_hostname="ctrl1"):
    """把 unix-socket HTTP 调用替换为内存路由表,socket 用真实存在的假文件。

    containers: 列表接口返回条目(Id/Labels);self_info: /containers/<HOSTNAME>/json
    的返回(用于自身 project 识别);engine 详情由 Id 自动生成最小结构。
    socket 路径必须是存在的文件(exists 探测用),连接本身已被 mock。
    """
    sock = tmp_path / "docker.sock"
    sock.touch()

    def fake_get(socket_path, path):
        if path.startswith("/containers/json"):
            return containers
        container_id = path.split("/")[2].split("?")[0]
        if container_id == self_hostname:
            if self_info is None:
                raise RuntimeError("docker api 404 on {0}".format(path))
            return self_info
        return {
            "Id": container_id,
            "Config": {"Env": ["ASCEND_RT_VISIBLE_DEVICES=0,1,2,3"]},
            "HostConfig": {},
        }

    monkeypatch.setattr(license_mod, "_http_get_over_unix_socket", fake_get)
    monkeypatch.setattr(license_mod, "DOCKER_SOCKET", sock)


def test_count_used_devices_excludes_own_project_engine(monkeypatch, tmp_path):
    """同 compose project 的 engine 正在等待本次授权,不得计入 used。

    回归:首启部署 engine 先起持有 4 卡等脚本,control 后跑门禁,旧行为
    used=4+request=4 > 6 恒超容。自识别统一打桩(真实 /proc/self/cgroup
    依赖沙箱自身环境,不可控)。
    """
    containers = [
        {"Id": "eng-self", "Labels": {"com.docker.compose.project": "proj-a"}},
        {"Id": "eng-other", "Labels": {"com.docker.compose.project": "proj-b"}},
    ]
    self_info = {"Config": {"Labels": {"com.docker.compose.project": "proj-a"}}}
    _fake_docker_api(monkeypatch, tmp_path, containers, self_info, self_hostname="selfid")
    monkeypatch.setattr(license_mod, "self_container_id", lambda **kwargs: "selfid")

    # 两个 engine 各 4 卡;同 project 的 eng-self 剔除,只计 proj-b 的 4 卡。
    assert license_mod.count_used_devices() == 4


def test_count_used_devices_counts_foreign_project_engines(monkeypatch, tmp_path):
    """不同 project 的 engine 是真实的已占用,必须计数。"""
    containers = [
        {"Id": "eng-b1", "Labels": {"com.docker.compose.project": "proj-b"}},
        {"Id": "eng-b2", "Labels": {"com.docker.compose.project": "proj-b"}},
    ]
    self_info = {"Config": {"Labels": {"com.docker.compose.project": "proj-a"}}}
    _fake_docker_api(monkeypatch, tmp_path, containers, self_info, self_hostname="selfid")
    monkeypatch.setattr(license_mod, "self_container_id", lambda **kwargs: "selfid")

    assert license_mod.count_used_devices() == 8


def test_count_used_devices_self_unknown_counts_all(monkeypatch, tmp_path):
    """识别不出自身容器(非容器环境/ID 解析失败)时不得剔除任何人。

    多计方向保守:宁可直接超容报错,不静默放宽配额。
    """
    containers = [
        {"Id": "eng-a", "Labels": {"com.docker.compose.project": "proj-a"}},
        {"Id": "eng-b", "Labels": {"com.docker.compose.project": "proj-b"}},
    ]
    _fake_docker_api(monkeypatch, tmp_path, containers, self_info=None)
    monkeypatch.setattr(license_mod, "self_container_id", lambda **kwargs: None)

    assert license_mod.count_used_devices() == 8


def test_count_used_devices_host_hostname_cp0_still_excludes_own(monkeypatch, tmp_path):
    """host 网络下 HOSTNAME 继承宿主机名(cp0)时,识别走 cgroup 路径。

    回归(实测):旧实现拿 HOSTNAME 查 API 必 404 → 自识别失败 → 自家
    engine 被计入 used → 一次性 up -d 恒 capacity_exceeded。新识别链从
    cgroup 拿真实容器 ID,HOSTNAME 为非 hex 宿主机名时被忽略。
    """
    real_id = "a" * 64
    containers = [
        {"Id": "eng-self", "Labels": {"com.docker.compose.project": "proj-a"}},
        {"Id": "eng-other", "Labels": {"com.docker.compose.project": "proj-b"}},
    ]
    self_info = {"Config": {"Labels": {"com.docker.compose.project": "proj-a"}}}
    _fake_docker_api(monkeypatch, tmp_path, containers, self_info, self_hostname=real_id)
    # 走生产的 proc 识别链,但把两个 /proc 路径指到 fixture 文件。
    cgroup = tmp_path / "cgroup"
    cgroup.write_text("11:cpu,cpuacct:/docker/{0}\n".format(real_id))
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text("")
    monkeypatch.setattr(license_mod, "_SELF_CGROUP_PATH", cgroup)
    monkeypatch.setattr(license_mod, "_SELF_MOUNTINFO_PATH", mountinfo)
    monkeypatch.setenv("HOSTNAME", "cp0")

    assert license_mod.count_used_devices() == 4
