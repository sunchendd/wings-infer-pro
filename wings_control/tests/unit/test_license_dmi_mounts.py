"""dmi_mounts_are_sysfs() 的 mountinfo 判定回归测试。

checker.c 的 C 实现无法在 pytest 里直接 import,这里维护一份逐行对应
的 Python 镜像(_Mirror),对内联 mountinfo 场景断言判定语义;C 实现
变更时必须同步本镜像,两侧不一致视为实现错误。

各场景为真实 mountinfo 格式的最小子集:字段 5 是挂载点," - " 之后
是 fstype,取自标准 Docker 容器与伪造部署的实测形态。
"""

import pytest

TARGETS = (
    "/host-sys/class/dmi/id/board_serial",
    "/sys/class/dmi/id/board_serial",
    "/sys/devices/virtual/dmi/id/board_serial",
)


class _Mirror:
    """checker.c dmi_mounts_are_sysfs() 的 Python 精确镜像。"""

    @staticmethod
    def parse_line(line):
        sep = line.find(" - ")
        if sep < 0:
            return None
        fields = line[:sep].split(" ")
        if len(fields) < 5:
            return None
        tail_start = sep + 3
        fstype = line[tail_start:].split(" ")[0]
        return fields[4].replace("\\040", " "), fstype

    @staticmethod
    def covers(mount_point, target):
        if not target.startswith(mount_point):
            return False
        length = len(mount_point)
        rest = target[length:]
        return rest == "" or rest.startswith("/")

    @classmethod
    def dmi_mounts_are_sysfs(cls, text):
        fstypes = [""] * len(TARGETS)
        matched = [0] * len(TARGETS)
        for line in text.splitlines():
            parsed = cls.parse_line(line)
            if parsed is None:
                continue
            mount_point, fstype = parsed
            length = len(mount_point)
            for index, target in enumerate(TARGETS):
                if cls.covers(mount_point, target) and length >= matched[index]:
                    matched[index] = length
                    fstypes[index] = fstype
        # 每条读路径的最长祖先挂载都必须是 sysfs(AND,非组内任一)。
        return all(m > 0 and f == "sysfs" for m, f in zip(matched, fstypes))


# (场景 id, mountinfo 文本, 预期)。
CASES = [
    # 标准容器:/sys 整树 sysfs 覆盖本地 class 拼写,host bind 是独立 sysfs 条目。
    # 修复前(要求挂载点在目标之下)该形态恒失败,即线上 esn_unavailable 的形态。
    (
        "standard",
        "\n".join(
            [
                "812 811 0:33 / / rw,relatime master:xx - overlay overlay rw,lowerdir=...",
                "813 812 0:34 / /sys ro,nosuid,nodev,noexec,relatime - sysfs sysfs ro",
                "814 812 0:35 / /host-sys/class/dmi/id rw,relatime - sysfs sysfs rw",
                "815 812 259:1 /var/lib/aiperf/license/adaptivelm "
                "/var/lib/aiperf/license/adaptivelm rw,relatime - ext4 /dev/sda1 rw",
                "816 813 0:36 / /sys/fs/cgroup ro,nosuid,nodev,noexec,relatime - tmpfs tmpfs ro",
            ]
        ),
        True,
    ),
    # host bind 为 class 拼写,本地另挂 devices 拼写独立 sysfs bind(部署侧
    # 手工补充挂载的形态),同样必须通过。
    (
        "local_devices_spelling",
        "\n".join(
            [
                "812 811 0:33 / / rw,relatime master:xx - overlay overlay rw,lowerdir=...",
                "813 812 0:34 / /sys ro,nosuid,nodev,noexec,relatime - sysfs sysfs ro",
                "814 812 0:35 / /host-sys/class/dmi/id rw,relatime - sysfs sysfs rw",
                "815 812 0:37 / /sys/devices/virtual/dmi/id rw,relatime - sysfs sysfs rw",
            ]
        ),
        True,
    ),
    # host bind 为 tmpfs 伪造目录:最长祖先匹配命中 tmpfs,拒。
    (
        "local_fake_dir",
        "\n".join(
            [
                "812 811 0:33 / / rw,relatime master:xx - overlay overlay rw,lowerdir=...",
                "813 812 0:34 / /sys ro,nosuid,nodev,noexec,relatime - sysfs sysfs ro",
                "814 812 0:36 / /host-sys/class/dmi/id rw,relatime - tmpfs tmpfs rw",
            ]
        ),
        False,
    ),
    # host bind 为 ext4 伪造目录 bind,拒。
    (
        "host_fake_dir",
        "\n".join(
            [
                "812 811 0:33 / / rw,relatime master:xx - overlay overlay rw,lowerdir=...",
                "813 812 0:34 / /sys ro,nosuid,nodev,noexec,relatime - sysfs sysfs ro",
                "814 812 259:1 /fake-dmi /host-sys/class/dmi/id rw,relatime - ext4 /dev/sda1 rw",
            ]
        ),
        False,
    ),
    # 伪造单文件 board_serial bind:它正是 host 路径更长的祖先匹配,拒。
    (
        "host_fake_file",
        "\n".join(
            [
                "812 811 0:33 / / rw,relatime master:xx - overlay overlay rw,lowerdir=...",
                "813 812 0:34 / /sys ro,nosuid,nodev,noexec,relatime - sysfs sysfs ro",
                "814 812 259:1 /fake/board_serial /host-sys/class/dmi/id/board_serial ro,relatime - ext4 /dev/sda1 ro",
            ]
        ),
        False,
    ),
]


@pytest.mark.parametrize("scenario,mountinfo,expected", CASES, ids=[c[0] for c in CASES])
def test_mountinfo_scenarios(scenario, mountinfo, expected):
    """合法部署形态通过,伪造挂载形态一律拒绝。"""
    assert _Mirror.dmi_mounts_are_sysfs(mountinfo) is expected


def test_class_shadowed_but_devices_real_is_rejected():
    """class 拼写被 tmpfs 顶替、devices 拼写真 sysfs 的绕过尝试必须拒绝。

    read_board_esn 读取路径是固定拼写,任一读路径可被非 sysfs 顶替都是
    防伪漏洞,故判定是全路径 AND 而非组内任一通过。
    """
    text = (
        "812 811 0:33 / / rw - overlay overlay rw\n"
        "813 812 0:34 / /sys ro - sysfs sysfs ro\n"
        "814 812 0:35 / /host-sys/class/dmi/id rw - sysfs sysfs rw\n"
        "815 812 0:36 / /sys/class/dmi/id rw - tmpfs tmpfs rw\n"
    )
    assert _Mirror.dmi_mounts_are_sysfs(text) is False


def test_missing_host_bind_fails_closed():
    """未挂 host bind(独立部署漏掉 override)时 host 路径无 sysfs 覆盖,拒。"""
    text = "812 811 0:33 / / rw - overlay overlay rw\n813 812 0:34 / /sys ro - sysfs sysfs ro\n"
    assert _Mirror.dmi_mounts_are_sysfs(text) is False


def test_empty_mountinfo_fails_closed():
    """mountinfo 无任何可匹配条目时 fail-closed。"""
    assert _Mirror.dmi_mounts_are_sysfs("") is False
