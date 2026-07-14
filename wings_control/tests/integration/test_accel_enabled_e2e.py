"""wings-accel enabled 端到端集成测试(真产出,非 stub)。

区别于 `tests/unit/test_accel_seam.py`(测 script_builder/emitter 接缝)与
`tests/integration/test_accel_merge_layer.py`(测 config_resolver 合并层机制,stub accel):
本测试用**真有 smart-accel yaml 资产**的组合 ``vllm / rtx_pro_5000_48G / Qwen3.5-397B-A17B / 0.23.0``,
跑**真 CLI**(不 mock accel),覆盖两条已有资产的特性:
- **投机解码** ``ENABLE_SPECULATIVE_DECODE`` → ``speculative_config`` 进 argv;``smart_decoding_scheme`` 进 audit。
- **KV 卸载** ``ENABLE_KV_OFFLOAD`` + ``KV_MEM_OFFLOAD_SIZE`` → ``kv_transfer_config`` 进 argv
  (``{mem_gb_to_bytes}`` 占位被真填成字节值;原生 vLLM(CUDA)≥v0.14 读 ``cpu_bytes_to_use``);
  ``smart_kv_cache_scheme`` 进 audit。
- 两特性同开 → **两段都并入**同一条 argv(建议3 合并层)。
- 全关 → accel no-op(argv/audit/install 段全无)。

> 稀疏(sparse)**当前无 yaml 资产**(assets 只含 decoding + kv_offload),故无法端到端验;
> 待 smart-accel 补 sparse 资产后再加(见 docs/45 §5.4)。

不执行生成的脚本(含 ``/accel-volume/install.py`` 行会失败),只读文本/JSON 断言。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wings_ctl import cli

_REPO_ROOT = Path(__file__).resolve().parents[2]
# 两侧都有资产的组合:wings-control recipe + smart-accel yaml
_ACCEL_ASSET = (
    _REPO_ROOT / "src" / "wings_accel" / "smart-accel" / "vllm" / "v0.23.0"
    / "rtx_pro_5000_48G" / "models" / "Qwen3.5-397B-A17B"
)
_RECIPE = _REPO_ROOT / "config" / "engines" / "vllm" / "rtx_pro_5000_48G" / "models" / "Qwen3.5-397B-A17B"
_HW = {"hardware_family": "rtx_pro_5000_48G", "device": "nvidia", "count": 1}

# 所有可能被本测试触碰的 accel/runtime env —— 每次跑前统一清空,保证场景隔离。
_ACCEL_ENV_KEYS = (
    "ENABLE_SPECULATIVE_DECODE", "SPECULATIVE_DECODE_MODEL_PATH",
    "ENABLE_KV_OFFLOAD", "ENABLE_KV_MEM_OFFLOAD", "KV_MEM_OFFLOAD_SIZE",
    "ENABLE_SPARSE", "SPARSE_LEVEL",
    "RANK_IP", "NODE_IPS", "MASTER_IP", "PD_ROLE",
)

_skip = pytest.mark.skipif(
    not _ACCEL_ASSET.exists() or not _RECIPE.exists(),
    reason="缺 smart-accel 资产或 wings-control recipe(vllm/rtx_pro_5000_48G/Qwen3.5-397B-A17B)",
)


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config_root_real: Path,
         *, accel_env: dict[str, str]):
    """跑真 CLI 产出三件套,返回 ``(start_command.sh 文本, audit dict)``。

    Args:
        accel_env: 本场景要下发的 MaaS accel 开关(如 ``{"ENABLE_KV_OFFLOAD": "true"}``);
            其余 accel/runtime env 一律清空(场景隔离)。

    Returns:
        (start_command.sh 全文, audit.json 解析后的 dict)。**不执行脚本**(含 install 行会报错)。
    """
    monkeypatch.setenv("ENGINE_VERSION", "0.23.0")
    for key in _ACCEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in accel_env.items():
        monkeypatch.setenv(key, value)

    out = tmp_path / "out"
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps(_HW), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl", "--model-name", "Qwen3.5-397B-A17B",
            "--config-root", str(config_root_real), "--hardware-info", str(hw),
            "--output-dir", str(out), "--engine", "vllm",
        ],
    )
    cli.main()
    start = (out / "start_command.sh").read_text(encoding="utf-8")
    audit = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    return start, audit


@_skip
def test_accel_speculative_enabled(tmp_path, monkeypatch, config_root_real):
    """开投机开关:accel 真产出 speculative_config → 进 argv;scheme 进 audit;install 段出现。"""
    start, audit = _run(tmp_path, monkeypatch, config_root_real,
                        accel_env={"ENABLE_SPECULATIVE_DECODE": "true"})
    assert "--speculative-config" in start
    assert '"method":"mtp"' in start.replace(" ", "")
    assert audit["wings_accel"]["smart_decoding_scheme"] == "mtp"
    # install 段(v6.3.3 §4.6"若启用"),版本= ENGINE_VERSION(契约 C-1);mtp 无依赖 → packages=[]
    assert "install.py --config" in start
    assert '"engine": {"name": "vllm", "version": "v0.23.0"}' in start
    assert '"packages": []' in start


@_skip
def test_accel_kv_offload_enabled(tmp_path, monkeypatch, config_root_real):
    """开 KV 卸载:accel 真产出 kv_transfer_config → 进 argv;占位被真填;scheme 进 audit。"""
    start, audit = _run(tmp_path, monkeypatch, config_root_real,
                        accel_env={"ENABLE_KV_OFFLOAD": "true", "KV_MEM_OFFLOAD_SIZE": "40"})
    compact = start.replace(" ", "")
    assert "--kv-transfer-config" in start
    assert '"kv_connector":"OffloadingConnector"' in compact
    # {mem_gb_to_bytes} 占位必须被真实字节值替换(不残留字面占位);CUDA 读 cpu_bytes_to_use
    assert "{mem_gb_to_bytes}" not in start
    assert '"cpu_bytes_to_use":"' in compact
    assert audit["wings_accel"]["smart_kv_cache_scheme"] == "cpu"
    # install 段:cpu = 原生 OffloadingConnector,无 lmcache 依赖 → packages=[](cpu 不需要 lmcache;
    # lmcache 包只在 disk/cpu_disk scheme 上,见 tests/wings_accel/test_offload.py)
    assert "install.py --config" in start
    assert '"packages": []' in start


@_skip
def test_accel_speculative_and_kv_offload_both_wired(tmp_path, monkeypatch, config_root_real):
    """两特性同开:speculative_config 与 kv_transfer_config **同时**并入一条 argv(合并层)。"""
    start, audit = _run(tmp_path, monkeypatch, config_root_real, accel_env={
        "ENABLE_SPECULATIVE_DECODE": "true",
        "ENABLE_KV_OFFLOAD": "true", "KV_MEM_OFFLOAD_SIZE": "40",
    })
    assert "--speculative-config" in start and "--kv-transfer-config" in start
    assert audit["wings_accel"]["smart_decoding_scheme"] == "mtp"
    assert audit["wings_accel"]["smart_kv_cache_scheme"] == "cpu"


@_skip
def test_accel_disabled_is_no_op(tmp_path, monkeypatch, config_root_real):
    """全关:accel 产空 → argv 无 accel 参数、audit 无 wings_accel、install 段不出现(gating 回归)。"""
    start, audit = _run(tmp_path, monkeypatch, config_root_real, accel_env={})
    assert "--speculative-config" not in start
    assert "--kv-transfer-config" not in start
    assert "install.py" not in start
    assert "wings_accel" not in audit


@_skip
def test_accel_dry_run_no_duplicate_speculative(tmp_path, monkeypatch, config_root_real, capsys):
    """回归:dry-run 打印的 argv 中 --speculative-config 只出现**一次**。

    docs/45 建议3 把 accel 改成 strategy_accel 合并层后,cli.py 的 dry-run/print 路径曾漏改、
    仍在 build_argv 之后额外 append `accel.engine_config`,导致 --speculative-config 重复(现场发现)。
    start_command.sh(script_builder)一直正确;bug 只在 cli.py 打印路径。本测试锁死单次。

    版本:DeepSeek-V4-Flash 的 smart-accel 投机资产在 v0.22.0(其 min_engine_version=0.22.0,
    见 src/wings_accel/smart-accel/vllm/v0.22.0/...);ENGINE_VERSION 必须对齐该版本才有 yaml 命中。
    """
    monkeypatch.setenv("ENGINE_VERSION", "0.22.0")
    for key in _ACCEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps(_HW), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl", "--model-name", "DeepSeek-V4-Flash",
            "--config-root", str(config_root_real), "--hardware-info", str(hw),
            "--engine", "vllm", "--dry-run",
        ],
    )
    cli.main()
    out = capsys.readouterr().out
    assert "--speculative-config" in out
    assert out.count("--speculative-config") == 1, f"--speculative-config 重复渲染:\n{out}"


@_skip
def test_dry_run_matches_start_command_exec(tmp_path, monkeypatch, config_root_real, capsys):
    """信任保证:dry-run 打印的命令 **逐字等于** start_command.sh 的 exec 行(去掉 'exec ')。

    两者都 `shlex.join(build_argv(同一 resolved))` → dry-run 所见即所落、可直接复制执行。
    用带 accel(speculative_config,含 JSON)的组合,同时压测合并层 + shlex 引号;
    这条断言能同时抓住"内容 drift"(如 accel 重复 append)与"格式 drift"(引号不一致)。
    """
    monkeypatch.setenv("ENGINE_VERSION", "0.23.0")
    for key in _ACCEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENABLE_SPECULATIVE_DECODE", "true")
    hw = tmp_path / "hw.json"
    hw.write_text(json.dumps(_HW), encoding="utf-8")
    base = [
        "wings-ctl", "--model-name", "DeepSeek-V4-Flash",
        "--config-root", str(config_root_real), "--hardware-info", str(hw), "--engine", "vllm",
    ]

    # 真路径落盘 → start_command.sh 的 exec 行
    out = tmp_path / "out"
    monkeypatch.setattr("sys.argv", base + ["--output-dir", str(out)])
    cli.main()
    capsys.readouterr()  # 清空 stdout
    start = (out / "start_command.sh").read_text(encoding="utf-8")
    start_exec = next(ln for ln in start.splitlines() if ln.startswith("exec vllm serve "))[len("exec "):]

    # dry-run → 打印的命令行
    monkeypatch.setattr("sys.argv", base + ["--dry-run"])
    cli.main()
    dry_line = next(ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("vllm serve "))

    assert dry_line == start_exec, f"dry-run 与 start exec 不一致:\ndry  : {dry_line}\nstart: {start_exec}"
