"""Mooncake store/master 脚本磁盘卸载开关行为测试。

磁盘卸载由 ``ENABLE_KV_DISK_OFFLOAD`` 决定(而非 ``KV_DISK_OFFLOAD_SIZE`` 非空):
env.yaml 容量默认 0,MaaS 契约在开关关闭时不下发容量,若默认非 0 或以 size 非空
判断,前端仅开内存卸载时会被误判为开启磁盘卸载。

本文件桩掉 python3 / mooncake_master(回显参数与 MOONCAKE_OFFLOAD* 环境),真实
执行随包脚本,断言参数校验、环境导出与启动参数分支;夹具脚本通过文本替换把
日志目录指向 tmp_path,并屏蔽与被测逻辑无关的环境探测(NPU master 的 so 拷贝、
NPU store 的 master 等待与 ascend 探测)。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

import wings_accel.distributed_offload as distributed_offload

_BASH = shutil.which("bash")
_ASSETS = Path(distributed_offload.__file__).parent / "distributed_offload"
_RUNTIMES = ["mooncake_cuda", "mooncake_npu"]
_STORE_LOG = "mooncake_store_setup.log"
_MASTER_LOG = "mooncake_master_setup.log"

# 容量层导出:仅在 ENABLE_KV_DISK_OFFLOAD=true 时出现
_CAPACITY_EXPORTS = [
    "MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES",
    "MOONCAKE_OFFLOAD_BUCKET_MAX_TOTAL_SIZE",
    "MOONCAKE_OFFLOAD_LOCAL_BUFFER_SIZE_BYTES",
    "MOONCAKE_OFFLOAD_HEARTBEAT_INTERVAL_SECONDS",
    "MOONCAKE_OFFLOAD_SLICE_MIN_THRESHOLD",
]

# 基础 backend 配置导出:与磁盘卸载开关无关(store 内存层始终需要),两个
# runtime 约定一致;仅容量层(_CAPACITY_EXPORTS)受 ENABLE_KV_DISK_OFFLOAD 控制。
_BASE_BACKEND_EXPORTS = [
    "MOONCAKE_OFFLOAD_SLICE_ENABLE",
    "MOONCAKE_OFFLOAD_OFFSET_ALLOCATOR_EVICTION_POLICY",
    "MOONCAKE_OFFLOAD_STORAGE_BACKEND_DESCRIPTOR",
    "MOONCAKE_OFFLOAD_FILE_STORAGE_PATH",
]

# 与被测变量同名的继承环境一律剥离,保证 client.env/master.env 夹具是唯一来源
_HERMETIC_STRIP = (
    "ENABLE_KV_OFFLOAD",
    "ENABLE_DISTRIBUTED_KV_OFFLOAD",
    "ENABLE_KV_MEM_OFFLOAD",
    "ENABLE_KV_DISK_OFFLOAD",
    "KV_MEM_OFFLOAD_SIZE",
    "KV_DISK_OFFLOAD_SIZE",
    "KV_DISK_OFFLOAD_PATH",
    "KV_PROTOCOL",
    "SERVING_CONFIG_ID",
)

pytestmark = pytest.mark.skipif(_BASH is None, reason="bash is required to execute mooncake scripts")


def _write_stubs(work: Path) -> None:
    """python3/mooncake_master 桩:回显启动参数并 dump MOONCAKE_OFFLOAD* 环境。"""
    stub_bin = work / "bin"
    stub_bin.mkdir(parents=True, exist_ok=True)
    (stub_bin / "python3").write_text(
        "#!/bin/bash\n"
        'echo "PYSTUB_ARGS: $*"\n'
        "env | grep '^MOONCAKE_OFFLOAD' | sort | sed 's/^/PYENV: /'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (stub_bin / "mooncake_master").write_text(
        "#!/bin/bash\n"
        'echo "MASTER_ARGS: $*"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    for stub in stub_bin.iterdir():
        stub.chmod(0o755)


def _prepare_script(runtime: str, script_name: str, work: Path) -> Path:
    """拷贝随包脚本并把日志/环境探测改指到 tmp_path;替换命中处带防御断言。"""
    text = (_ASSETS / runtime / script_name).read_text(encoding="utf-8")
    text = text.replace("LOG_PATH=/var/log/wings", f"LOG_PATH={work}")
    text = text.replace(
        "function monitor_server() {",
        "function monitor_server() { start_server; }\nfunction _stubbed_monitor_server() {",
    )
    assert "_stubbed_monitor_server" in text, "monitor_server stub did not apply"
    if runtime == "mooncake_npu":
        if script_name == "start_mooncake_store.sh":
            # 单测环境无 master/NPU:屏蔽等待与 ascend 探测(均非被测逻辑)
            text = text.replace(
                "function wait_for_master() {",
                "function wait_for_master() { return 0; }\nfunction _stubbed_wait_for_master() {",
            )
            text = text.replace(
                "function set_ascend_env() {",
                "function set_ascend_env() { return 0; }\nfunction _stubbed_set_ascend_env() {",
            )
            assert "_stubbed_wait_for_master" in text and "_stubbed_set_ascend_env" in text
        else:
            # 单测不依赖容器内 Ascend so，按函数边界屏蔽镜像适配拷贝。
            text = text.replace(
                "function pre_handler() {",
                "function pre_handler() { return 0; }\nfunction _stubbed_pre_handler() {",
            )
            assert "_stubbed_pre_handler" in text, "pre_handler stub did not apply"
    assert f"LOG_PATH={work}" in text, "log path patch did not apply"
    target = work / script_name
    target.write_text(text, encoding="utf-8")
    return target


def _script_env(work: Path) -> dict:
    env = {key: value for key, value in os.environ.items() if key not in _HERMETIC_STRIP}
    env["PATH"] = f"{work / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    return env


def _run(script: Path, work: Path) -> subprocess.CompletedProcess:
    return subprocess.run([_BASH, str(script)], env=_script_env(work), capture_output=True, text=True)


def _output(work: Path, log_name: str, proc: subprocess.CompletedProcess) -> str:
    """脚本重定向到日志文件的内容 + 进程 stdout/stderr,合并供断言。"""
    log = work / log_name
    time.sleep(1)  # NPU store 以 & 启动 python3,留出桩回显落盘时间
    parts = [proc.stdout, proc.stderr]
    if log.is_file():
        parts.append(log.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _write_client_env(work: Path, **overrides) -> None:
    values = {
        "ENABLE_KV_MEM_OFFLOAD": "true",
        "KV_MEM_OFFLOAD_SIZE": "32",
        "KV_PROTOCOL": "rdma",
        "SERVING_CONFIG_ID": "switch-test",
        "ENABLE_KV_DISK_OFFLOAD": "false",
        "KV_DISK_OFFLOAD_SIZE": "0",
    }
    values.update(overrides)
    (work / "client.env").write_text(
        "\n".join(f"export {key}={value}" for key, value in sorted(values.items())) + "\n",
        encoding="utf-8",
    )


def _write_master_env(work: Path, **overrides) -> None:
    values = {"MOONCAKE_MASTER_PORT": "50051"}
    values.update(overrides)
    (work / "master.env").write_text(
        "\n".join(f"export {key}={value}" for key, value in sorted(values.items())) + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("runtime", _RUNTIMES)
def test_env_yaml_disk_capacity_defaults_stay_closed(runtime):
    """env.yaml 容量默认必须为 0 且 master 段携带开关:false 场景不得静默开磁盘卸载。

    回归锚点:容量默认曾是 "11",前端仅开内存卸载(MaaS 不下发磁盘变量)时
    client.env 落到默认 11,store 脚本按 size 非空误开磁盘卸载。
    """
    import yaml

    data = yaml.safe_load((_ASSETS / runtime / "env.yaml").read_text(encoding="utf-8"))
    assert data["client"]["KV_DISK_OFFLOAD_SIZE"] == "0"
    assert data["client"]["KV_MEM_OFFLOAD_SIZE"] == "0"
    # master.env 携带开关:start_mooncake_master.sh 依赖它决定 --enable-offload
    assert data["master"]["ENABLE_KV_DISK_OFFLOAD"] == "false"


@pytest.mark.parametrize("runtime", _RUNTIMES)
def test_store_mem_only_does_not_enable_disk_offload(runtime, tmp_path):
    """仅内存卸载(开关 false + 容量 0)→ 无容量层导出、启动参数不带 --offload-dir。"""
    work = tmp_path / runtime
    work.mkdir()
    _write_stubs(work)
    script = _prepare_script(runtime, "start_mooncake_store.sh", work)
    _write_client_env(work)

    proc = _run(script, work)
    output = _output(work, _STORE_LOG, proc)
    assert proc.returncode == 0, output

    assert "--offload-dir" not in output
    for name in _CAPACITY_EXPORTS:
        assert name not in output, f"disk offload closed but {name} exported"
    assert "disk offload false" in output
    # 基础 backend 配置与开关无关(见 _BASE_BACKEND_EXPORTS 注释)
    for name in _BASE_BACKEND_EXPORTS:
        assert f"PYENV: {name}=" in output


@pytest.mark.parametrize("runtime", _RUNTIMES)
def test_store_disk_offload_enabled_exports_capacity_and_offload_dir(runtime, tmp_path):
    """开关 true + 容量 128GB → 容量按字节导出,store 启动参数带 --offload-dir。"""
    work = tmp_path / runtime
    work.mkdir()
    _write_stubs(work)
    script = _prepare_script(runtime, "start_mooncake_store.sh", work)
    _write_client_env(work, ENABLE_KV_DISK_OFFLOAD="true", KV_DISK_OFFLOAD_SIZE="128")

    proc = _run(script, work)
    output = _output(work, _STORE_LOG, proc)
    assert proc.returncode == 0, output

    assert "--offload-dir /tmp/kvcacheoffload" in output
    assert "PYENV: MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES=137438953472" in output  # 128GB
    assert "PYENV: MOONCAKE_OFFLOAD_SLICE_MIN_THRESHOLD=104857600" in output  # 100MB
    assert "disk offload true" in output


@pytest.mark.parametrize("runtime", _RUNTIMES)
def test_store_rejects_invalid_disk_offload_switch(runtime, tmp_path):
    """开关值非法(非 true/false 族)→ 报错指明变量名并 exit 1。"""
    work = tmp_path / runtime
    work.mkdir()
    _write_stubs(work)
    script = _prepare_script(runtime, "start_mooncake_store.sh", work)
    _write_client_env(work, ENABLE_KV_DISK_OFFLOAD="yes", KV_DISK_OFFLOAD_SIZE="128")

    proc = _run(script, work)
    output = _output(work, _STORE_LOG, proc)
    assert proc.returncode == 1, output
    assert "ENABLE_KV_DISK_OFFLOAD=yes" in output


@pytest.mark.parametrize("runtime", _RUNTIMES)
@pytest.mark.parametrize("size", ["0", ""])
def test_store_rejects_enabled_switch_without_positive_size(runtime, size, tmp_path):
    """开关 true 但容量缺失/为 0 → 报错指明 KV_DISK_OFFLOAD_SIZE 并 exit 1。"""
    work = tmp_path / runtime
    work.mkdir()
    _write_stubs(work)
    script = _prepare_script(runtime, "start_mooncake_store.sh", work)
    _write_client_env(work, ENABLE_KV_DISK_OFFLOAD="true", KV_DISK_OFFLOAD_SIZE=size)

    proc = _run(script, work)
    output = _output(work, _STORE_LOG, proc)
    assert proc.returncode == 1, output
    assert "KV_DISK_OFFLOAD_SIZE" in output


@pytest.mark.parametrize("runtime", _RUNTIMES)
@pytest.mark.parametrize(
    "switch,expected_flag",
    [("false", "--enable-offload=false"), ("true", "--enable-offload=true")],
)
def test_master_enable_offload_follows_switch(runtime, switch, expected_flag, tmp_path):
    """--enable-offload 跟随 master.env 的 ENABLE_KV_DISK_OFFLOAD,不再硬编码 true。"""
    work = tmp_path / runtime
    work.mkdir()
    _write_stubs(work)
    script = _prepare_script(runtime, "start_mooncake_master.sh", work)
    _write_master_env(work, ENABLE_KV_DISK_OFFLOAD=switch)

    proc = _run(script, work)
    output = _output(work, _MASTER_LOG, proc)
    assert proc.returncode == 0, output
    assert expected_flag in output
    if switch == "true":
        assert "--enable-offload=false" not in output


def test_master_enable_offload_defaults_to_false_when_switch_missing(tmp_path):
    """master.env 缺开关(env.yaml 渲染兜底失效的防御路径)→ 按 false 处理。"""
    runtime = "mooncake_cuda"
    work = tmp_path / runtime
    work.mkdir()
    _write_stubs(work)
    script = _prepare_script(runtime, "start_mooncake_master.sh", work)
    _write_master_env(work)

    proc = _run(script, work)
    output = _output(work, _MASTER_LOG, proc)
    assert proc.returncode == 0, output
    assert "--enable-offload=false" in output


@pytest.mark.parametrize("runtime", _RUNTIMES)
def test_master_rejects_invalid_disk_offload_switch(runtime, tmp_path):
    """开关值非法 → 报错指明变量名并 exit 1。"""
    work = tmp_path / runtime
    work.mkdir()
    _write_stubs(work)
    script = _prepare_script(runtime, "start_mooncake_master.sh", work)
    _write_master_env(work, ENABLE_KV_DISK_OFFLOAD="maybe")

    proc = _run(script, work)
    output = _output(work, _MASTER_LOG, proc)
    assert proc.returncode == 1, output
    assert "ENABLE_KV_DISK_OFFLOAD=maybe" in output
