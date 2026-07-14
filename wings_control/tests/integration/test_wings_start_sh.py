"""wings_start.sh 入口集成测试 —— 确保项目可经 shell 薄壳真正拉起(端到端)。

直接以子进程跑 ``bash wings_start.sh <args>``,验证薄壳的 python 探测 / PYTHONPATH 设置 /
参数透传都正确,并产出三件产物。区别于其它测试直调 python 模块,本测试覆盖**真实入口**。
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

# tests/integration/<this> → 仓库根
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "wings_start.sh"


def _hw(tmp_path: Path) -> Path:
    p = tmp_path / "hardware_info.json"
    p.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    return p


def _run(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess:
    """以子进程跑 wings_start.sh;ENGINE_VERSION 固定,日志指向 tmp 避免 /var/log 噪音。"""
    env = dict(os.environ)
    env["ENGINE_VERSION"] = "0.18.0"
    env["WINGS_START_LOG"] = str(tmp_path / "wings_start.log")
    # 清掉可能从外部泄漏的多机运行时上下文,确保走 standalone
    for k in ("RANK_IP", "NODE_IPS", "MASTER_IP", "PD_ROLE"):
        env.pop(k, None)
    return subprocess.run(
        ["bash", str(_SCRIPT), *args],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def _start(args: list[str], tmp_path: Path) -> subprocess.Popen[str]:
    """以长驻模式启动 wings_start.sh。

    成功路径下 ``wings_start.sh`` 会继续拉起 proxy/health 并常驻，因此测试不能再用
    ``subprocess.run()`` 等待其自然退出；这里改为 ``Popen``，由测试在观察到"启动成功"
    后主动收尾。

    Args:
        args: 传给 ``wings_start.sh`` 的命令行参数。
        tmp_path: 当前用例的临时目录，用于隔离日志和产物。

    Returns:
        长驻中的子进程句柄。
    """
    env = dict(os.environ)
    env["ENGINE_VERSION"] = "0.18.0"
    env["WINGS_START_LOG"] = str(tmp_path / "wings_start.log")
    for k in ("RANK_IP", "NODE_IPS", "MASTER_IP", "PD_ROLE"):
        env.pop(k, None)
    return subprocess.Popen(
        ["bash", str(_SCRIPT), *args],
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )


def _wait_for_artifacts(proc: subprocess.Popen[str], out_dir: Path, timeout_sec: float = 15.0) -> None:
    """等待 wings_start.sh 把三件产物落盘(不要求 proxy 真正起来)。

    ``wings_start.sh`` 默认在生成产物后继续启动 proxy;proxy 能否起来取决于运行解释器是否装了
    proxy 依赖(I20:系统 ``python3`` 常缺 ``pydantic``)。**但三件产物是在 CLI 阶段、proxy import
    之前就写好的**,所以本函数只等产物出现即视为成功——无论其后 proxy 长驻还是因缺依赖退出。
    这样测试聚焦"生成 + 透传",不与 proxy 运行时依赖耦合(见 docs/14 I20)。

    Args:
        proc: ``_start()`` 返回的子进程。
        out_dir: 产物目录。
        timeout_sec: 最长等待时长。

    Raises:
        AssertionError: 子进程在产物落盘前就退出,或超时仍无产物。
    """
    deadline = time.time() + timeout_sec
    artifacts = [out_dir / "start_command.sh", out_dir / "repro.sh", out_dir / "audit.json"]
    while time.time() < deadline:
        if all(path.exists() for path in artifacts):
            return  # 产物已落盘(CLI 阶段完成)→ 成功,不管 proxy 之后长驻还是退出
        if proc.poll() is not None:
            # 进程退出且产物仍未齐 → CLI 自身失败
            stdout, stderr = proc.communicate(timeout=5)
            raise AssertionError(f"进程在产物落盘前退出\nstdout={stdout}\nstderr={stderr}")
        time.sleep(0.2)
    _stop_process(proc)
    stdout, stderr = proc.communicate(timeout=5)
    raise AssertionError(f"超时仍无产物\nstdout={stdout}\nstderr={stderr}")


def _stop_process(proc: subprocess.Popen[str]) -> None:
    """结束由 ``_start()`` 拉起的长驻进程组。

    Args:
        proc: 待结束的长驻进程。
    """
    if proc.poll() is not None:
        return
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)


@pytest.mark.skipif(not _SCRIPT.exists(), reason="wings_start.sh 不在仓库根")
def test_wings_start_sh_produces_artifacts(config_root_real, tmp_path):
    """验证 bash wings_start.sh 默认起 proxy，同时先产出三件产物。"""
    out = tmp_path / "out"
    proc = _start(
        [
            "--engine", "vllm-ascend",
            "--model-name", "DeepSeek-V4-Flash",
            "--config-root", str(config_root_real),
            "--hardware-info", str(_hw(tmp_path)),
            "--port", "18000",
            "--output-dir", str(out),
        ],
        tmp_path,
    )
    try:
        _wait_for_artifacts(proc, out)
    finally:
        _stop_process(proc)
        proc.communicate(timeout=5)
    assert (out / "start_command.sh").exists()
    assert (out / "repro.sh").exists()
    assert (out / "audit.json").exists()
    assert "vllm serve" in (out / "start_command.sh").read_text(encoding="utf-8")


@pytest.mark.skipif(not _SCRIPT.exists(), reason="wings_start.sh 不在仓库根")
def test_wings_start_sh_forwards_args_to_cli(config_root_real, tmp_path):
    """验证薄壳把参数原样透传，且默认长驻 proxy 不影响 audit 落盘。"""
    out = tmp_path / "out"
    proc = _start(
        [
            "--engine", "vllm-ascend",
            "--model-name", "DeepSeek-V4-Flash",
            "--config-root", str(config_root_real),
            "--hardware-info", str(_hw(tmp_path)),
            "--port", "18000",
            "--max-num-batched-tokens", "4096",
            "--output-dir", str(out),
        ],
        tmp_path,
    )
    try:
        _wait_for_artifacts(proc, out)
    finally:
        _stop_process(proc)
        proc.communicate(timeout=5)
    audit = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    entry = audit["engine_config"]["max_num_batched_tokens"]
    assert entry["final_value"] == 4096 and entry["final_layer"] == "user_cli"


@pytest.mark.skipif(not _SCRIPT.exists(), reason="wings_start.sh 不在仓库根")
def test_wings_start_sh_friendly_error_propagates_nonzero(config_root_real, tmp_path):
    """验证缺配方标识(无 --model-name / --model-path)时薄壳透传非零退出 + 友好报错。"""
    proc = _run(
        [
            "--engine", "vllm-ascend",
            "--config-root", str(config_root_real),
            "--hardware-info", str(_hw(tmp_path)),
            "--output-dir", str(tmp_path / "out"),
        ],
        tmp_path,
    )
    assert proc.returncode != 0
