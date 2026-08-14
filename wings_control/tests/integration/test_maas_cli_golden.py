from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from tests.script_test_utils import run_vllm_command_as_echo
from wings_ctl import cli


# Golden maintenance note:
# If config/recipe changes intentionally, refresh golden by re-running the exact
# same CLI inputs in this file and replace tests/integration/golden/*.argv with
# the real argv output. Updating golden is an explicit baseline confirmation step.
GOLDEN_DIR = Path(__file__).parent / "golden"


@dataclass(frozen=True)
class GoldenScene:
    name: str
    engine: str
    engine_version: str
    hardware: dict[str, object]
    model_resolver: Callable[[Path, Path, pytest.MonkeyPatch], str]
    cli_args: list[str]
    golden_file: str
    must_contain: list[str]


def _constant_model(name: str) -> Callable[[Path, Path, pytest.MonkeyPatch], str]:
    def _resolver(_config_root: Path, _tmp_path: Path, _monkeypatch: pytest.MonkeyPatch) -> str:
        return name

    return _resolver


def _pick_h200_model_with_default_strategy(
    config_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    base = config_root / "engines" / "vllm" / "h200" / "models"
    assert base.exists(), f"h200 models dir missing: {base}"

    hw_path = tmp_path / "h200_hardware_probe.json"
    hw_path.write_text(
        json.dumps({"hardware_family": "h200", "device": "nvidia", "count": 8}),
        encoding="utf-8",
    )

    for yaml_path in sorted(base.rglob("*.yaml")):
        content = yaml_path.read_text(encoding="utf-8")
        if "strategies:" not in content:
            continue
        if "default_strategy:" not in content:
            continue
        if "gpu_memory_utilization:" not in content:
            continue

        for candidate_model in (yaml_path.parent.name, yaml_path.stem):
            probe_out = tmp_path / f"probe_{candidate_model}"
            monkeypatch.setenv("ENGINE_VERSION", "0.19.0")
            monkeypatch.setattr(
                "sys.argv",
                [
                    "wings-ctl",
                    "--model-name",
                    candidate_model,
                    "--config-root",
                    str(config_root),
                    "--hardware-info",
                    str(hw_path),
                    "--output-dir",
                    str(probe_out),
                    "--engine",
                    "vllm",
                    "--dry-run",
                ],
            )
            try:
                cli.main()
                return candidate_model
            except (SystemExit, ValueError):
                continue

    raise AssertionError("No h200 strategies+default_strategy model can be resolved by CLI")


def _run_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config_root_real: Path,
    *,
    engine: str,
    model: str,
    hw_dict: dict[str, object],
    engine_version: str,
    cli_args: list[str],
) -> tuple[str, dict]:
    scene_out = tmp_path / f"out_{engine}_{model.replace('/', '_')}"
    hardware_info = tmp_path / f"hardware_{engine}.json"
    hardware_info.write_text(json.dumps(hw_dict), encoding="utf-8")

    monkeypatch.setenv("ENGINE_VERSION", engine_version)
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl",
            "--model-name",
            model,
            "--config-root",
            str(config_root_real),
            "--hardware-info",
            str(hardware_info),
            "--output-dir",
            str(scene_out),
            "--engine",
            engine,
            *cli_args,
        ],
    )
    cli.main()

    start_path = scene_out / "start_command.sh"
    audit_path = scene_out / "audit.json"
    assert start_path.exists(), f"missing start_command.sh: {start_path}"
    assert audit_path.exists(), f"missing audit.json: {audit_path}"

    command = run_vllm_command_as_echo(start_path)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    return command, audit


def _assert_recipe_agnostic_invariants(argv: str, audit: dict) -> None:
    assert argv.startswith("vllm serve ")
    # served_model_name = --model-name(模型名称),具体值由 golden 逐字断言;此处只验存在
    assert "--served-model-name " in argv
    assert "--port 17000" in argv   # proxy 迁移:用户 --port 18000 是 proxy 端口,engine argv 为 backend 17000
    # 评审定:gpu_memory_utilization / seed 直通(user_cli 覆盖 recipe)→ 用户特异值出现在 argv
    assert "--gpu-memory-utilization 0.55" in argv
    assert "--seed 12345" in argv

    rows = audit.get("user_cli_params", [])
    assert isinstance(rows, list)
    assert "dropped_user_params" not in audit

    row_by_key = {str(row.get("key")): row for row in rows}
    for applied_key in ("served_model_name", "port", "gpu_memory_utilization", "seed"):
        row = row_by_key.get(applied_key)
        assert row is not None, f"missing user_cli_params row for {applied_key}"
        assert row.get("status") == "applied"

    for dropped_key in ("input_length", "output_length"):   # 仅这两个仍丢弃(vllm 无对应)
        row = row_by_key.get(dropped_key)
        assert row is not None, f"missing user_cli_params row for {dropped_key}"
        assert row.get("status") == "dropped"
        assert row.get("reason"), f"dropped key {dropped_key} missing reason"

    # gpu_memory_utilization 现由 user_cli 覆盖 recipe(user_cli 最高优先级)
    assert audit["engine_config"]["gpu_memory_utilization"]["final_layer"] == "user_cli"
    assert audit["engine_config"]["seed"]["final_layer"] == "user_cli"


_COMMON_NAMED_ARGS = [
    # 注:--model-name 由 _run_cli 用 scene 的 model 提供(=模型名称+served);此处不再单列
    "--port",
    "18000",
    "--max-num-seqs",
    "256",
    "--trust-remote-code",
    "--input-length",
    "4096",
    "--output-length",
    "4096",
    "--gpu-memory-utilization",
    "0.55",
    "--seed",
    "12345",
]


@pytest.mark.parametrize(
    "scene",
    [
        GoldenScene(
            name="scene-a-vllm-ascend",
            engine="vllm-ascend",
            engine_version="0.18.0",
            hardware={"hardware_family": "ascend-a3", "device": "ascend", "count": 16},
            model_resolver=_constant_model("DeepSeek-V4-Flash"),
            cli_args=list(_COMMON_NAMED_ARGS),
            golden_file="scene_a_vllm_ascend.argv",
            must_contain=[
                "vllm serve /root/.cache/modelscope/hub/models/vllm-ascend/DeepSeek-V4-Flash-w8a8-mtp",
                "--served-model-name DeepSeek-V4-Flash",
                "--max-num-seqs 256",
            ],
        ),
        GoldenScene(
            name="scene-b-vllm-h200",
            engine="vllm",
            engine_version="0.19.0",
            hardware={"hardware_family": "h200", "device": "nvidia", "count": 8},
            # 钉死模型:golden 逐字断言要求确定性输入,不能用"自动挑选"(config 变更会换模型 → 假报错)。
            # 自动挑选能力另由 test_h200_default_strategy_model_is_resolvable 冒烟覆盖。
            # 传完整变体名 variant_name(docs/48):h200 下 DeepSeek-V4-Pro 有 fp8/dspark 两变体,
            # 传家族名会命中歧义;--model-name 同时成为 --served-model-name。
            model_resolver=_constant_model("DeepSeek-V4-Pro-fp8"),
            cli_args=list(_COMMON_NAMED_ARGS),
            golden_file="scene_b_vllm_h200.argv",
            must_contain=[
                "vllm serve ",
                "--served-model-name DeepSeek-V4-Pro-fp8",
                "--max-num-seqs 256",
            ],
        ),
    ],
    ids=lambda s: s.name,
)
def test_maas_cli_golden_and_invariants(
    scene: GoldenScene,
    config_root_real: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = scene.model_resolver(config_root_real, tmp_path, monkeypatch)
    print(f"[golden] {scene.name} selected model: {model}")
    argv, audit = _run_cli(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        config_root_real=config_root_real,
        engine=scene.engine,
        model=model,
        hw_dict=scene.hardware,
        engine_version=scene.engine_version,
        cli_args=scene.cli_args,
    )

    golden_path = GOLDEN_DIR / scene.golden_file
    assert golden_path.exists(), f"missing golden file: {golden_path}"
    golden_argv = golden_path.read_text(encoding="utf-8").strip()
    assert argv == golden_argv

    for token in scene.must_contain:
        assert token in argv
    for dropped_token in ("input-length", "output-length"):   # gpu 0.55 / seed 12345 现已直通进 argv
        assert dropped_token not in argv

    _assert_recipe_agnostic_invariants(argv, audit)


def test_full_maas_param_passdown(
    config_root_real: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_args = [
        # --model-name 由 _run_cli 用 model=DeepSeek-V4-Flash 提供(=模型名称+served)
        "--model-path",
        "/maas/models/ds",
        "--host",
        "0.0.0.0",
        "--port",
        "18000",
        "--dtype",
        "float16",
        "--kv-cache-dtype",
        "fp8",
        "--quantization",
        "awq",
        "--quantization-param-path",
        "/q.json",
        "--gpu-memory-utilization",
        "0.55",
        "--block-size",
        "32",
        "--max-num-seqs",
        "256",
        "--seed",
        "12345",
        "--input-length",
        "4096",
        "--output-length",
        "4096",
        "--trust-remote-code",
        "--enable-chunked-prefill",
        "--enable-prefix-caching",
        "--enable-expert-parallel",
        "--enable-auto-tool-choice",
        "--enable-auto-think-choice",
        "--device-count",
        "8",
    ]
    argv, audit = _run_cli(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        config_root_real=config_root_real,
        engine="vllm-ascend",
        model="DeepSeek-V4-Flash",
        hw_dict={"hardware_family": "ascend-a3", "device": "ascend", "count": 16},
        engine_version="0.18.0",
        cli_args=full_args,
    )

    rows = audit.get("user_cli_params", [])
    row_by_key = {str(row.get("key")): row for row in rows}

    # 评审定(2026-06):原"删掉(不覆盖基线)"一组改 applied(直通,user_cli 覆盖 recipe);
    # input/output_length(vllm 无对应)dropped;**两个特性开关 enable_auto_{tool,think}_choice**
    # 自 Step3.2 起为 FeatureOverlay 开关 → 从 user_cli 渲染层 dropped(真正 --tool-call-parser/
    # --enable-auto-tool-choice 由 features 块或 recipe inline 提供,见 docs/39 §7.0a)。
    expected_status = {
        "served_model_name": "applied",
        "model": "applied",
        "host": "applied",
        "port": "applied",
        "max_num_seqs": "applied",
        "trust_remote_code": "applied",
        "enable_auto_tool_choice": "dropped",
        "dtype": "applied",
        "kv_cache_dtype": "applied",
        "quantization": "dropped",
        "quantization_param_path": "applied",
        "gpu_memory_utilization": "applied",
        "block_size": "applied",
        "seed": "applied",
        "enable_chunked_prefill": "applied",
        "enable_prefix_caching": "dropped",
        "enable_expert_parallel": "dropped",
        "input_length": "dropped",
        "output_length": "dropped",
        "enable_auto_think_choice": "dropped",
    }

    # 可展示输出(pytest -s 时打印):全量 MaaS 启动参数逐条处置表,供评审现场查看。
    print("\n=== 全量 MaaS 启动参数下发 → 处置(engine=vllm-ascend model=DeepSeek-V4-Flash)===")
    print(f"  {'native_key':28}{'处置':10}reason / 备注")
    print(f"  {'-' * 28}{'-' * 10}{'-' * 30}")
    for key, status in expected_status.items():
        reason = str(row_by_key.get(key, {}).get("reason", ""))
        note = reason if status == "dropped" else "用户值生效(applied)"
        print(f"  {key:28}{status:10}{note}")
    print(f"  {'device_count':28}{'audit-only':10}写 resolution_notes="
          f"{audit['resolution_notes'].get('device_count')},不参与 DP 计算(I15)")
    applied_n = sum(1 for s in expected_status.values() if s == "applied")
    dropped_n = sum(1 for s in expected_status.values() if s == "dropped")
    print(f"  小结:applied={applied_n} dropped={dropped_n}(均带 reason);用户特异值未泄漏 argv\n")

    for key, status in expected_status.items():
        row = row_by_key.get(key)
        assert row is not None, f"missing user_cli_params key: {key}"
        assert row.get("status") == status, f"{key} status mismatch"
        if status == "dropped":
            assert row.get("reason"), f"dropped key {key} missing reason"

    assert (
        row_by_key["quantization"].get("reason")
        == "maas_status=not_in_maas_contract_allowlist"
    )
    assert (
        row_by_key["enable_prefix_caching"].get("reason")
        == "maas_status=not_in_maas_contract_allowlist"
    )
    assert (
        row_by_key["enable_expert_parallel"].get("reason")
        == "maas_status=not_in_maas_contract_allowlist"
    )
    assert "FeatureOverlay" in str(row_by_key["enable_auto_think_choice"].get("reason"))
    assert "FeatureOverlay" in str(row_by_key["enable_auto_tool_choice"].get("reason"))
    # argv 里 tool 调用参数来自 recipe inline(D2:无开关随 model.yaml),不因开关 dropped 而消失
    assert "--enable-auto-tool-choice" in argv
    assert "--tool-call-parser" in argv
    assert int(audit["resolution_notes"]["device_count"]) == 8
    # gpu_memory_utilization 现由 user_cli 覆盖 recipe(user_cli 最高优先级)
    assert audit["engine_config"]["gpu_memory_utilization"]["final_layer"] == "user_cli"

    assert "chat-template-kwargs" not in argv
    assert "enable_thinking" not in argv
    assert "enable-auto-think" not in argv


def test_h200_default_strategy_model_is_resolvable(
    config_root_real: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """冒烟:h200 下能自动定位到 strategies+default_strategy 模型并被 CLI 解析。

    与 golden 逐字断言解耦——只验"自动选默认策略模型"能力,不绑具体输出。
    """
    model = _pick_h200_model_with_default_strategy(config_root_real, tmp_path, monkeypatch)
    assert model


def test_device_count_computes_dp(
    config_root_real: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """device_count × DP 协调(I15 Phase3,docs/03 D 受限例外)。

    DeepSeek-V4-Flash 模板 TP(M)=4。不同 device_count → DP=cnt//M:
      cnt=8 → DP=2,cnt=12 → DP=3(均 ≠ 模板 4 → 走 strategy_device_count 覆盖层)。
    TP 静态不变;改写经独立 trace 层,final_layer=strategy_device_count(不冒充 model_scenario)。
    """
    import re

    def _flag(argv: str, flag: str) -> str | None:
        m = re.search(rf"{re.escape(flag)}\s+(\S+)", argv)
        return m.group(1) if m else None

    common = dict(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        config_root_real=config_root_real,
        engine="vllm-ascend",
        model="DeepSeek-V4-Flash",
        hw_dict={"hardware_family": "ascend-a3", "device": "ascend", "count": 16},
        engine_version="0.18.0",
    )
    base_args = ["--port", "18000"]  # --model-name 由 _run_cli 提供(model=DeepSeek-V4-Flash)

    argv8, audit8 = _run_cli(**common, cli_args=base_args + ["--device-count", "8"])
    argv12, audit12 = _run_cli(**common, cli_args=base_args + ["--device-count", "12"])

    # 可展示输出(pytest -s):DeviceCountTransform 协调结果
    print("\n=== DeviceCountTransform 演示(DeepSeek-V4-Flash,模板 TP=4)===")
    print(f"  --device-count 8  → data-parallel-size={_flag(argv8, '--data-parallel-size')} "
          f"/ tensor-parallel-size={_flag(argv8, '--tensor-parallel-size')}(静态)"
          f" / final_layer={audit8['engine_config']['data_parallel_size']['final_layer']}")
    print(f"  --device-count 12 → data-parallel-size={_flag(argv12, '--data-parallel-size')} "
          f"/ tensor-parallel-size={_flag(argv12, '--tensor-parallel-size')}(静态)")
    print("  → DP=cnt//TP 随 device-count 变,TP 静态不动,改写归 strategy_device_count 层\n")

    # 留底:device_count 写 audit
    assert int(audit8["resolution_notes"]["device_count"]) == 8
    assert int(audit12["resolution_notes"]["device_count"]) == 12

    # 算 DP:DP=cnt//M(M=4)→ 2 与 3,随 device_count 变
    assert _flag(argv8, "--data-parallel-size") == "2"
    assert _flag(argv12, "--data-parallel-size") == "3"
    # TP 静态:绝不随 device_count 改变
    assert _flag(argv8, "--tensor-parallel-size") == "4"
    assert _flag(argv12, "--tensor-parallel-size") == "4"

    # 全 trace:DP 改写归到 strategy 层,不冒充 model_scenario
    dp_trace = audit8["engine_config"]["data_parallel_size"]
    assert dp_trace["final_value"] == 2
    assert dp_trace["final_layer"] == "strategy_device_count"
    layers = [e["layer"] for e in dp_trace["events"]]
    assert "model_scenario" in layers and "strategy_device_count" in layers

    # resolution_notes 协调摘要
    assert audit8["resolution_notes"]["device_count_resolved_dp"] == "2"
    assert audit8["resolution_notes"]["device_count_status"] == "overridden"

    # device_count 本身不进 argv
    assert "--device-count" not in argv8


def test_device_count_below_tp_raises_friendly_cli_error(
    config_root_real: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """cnt<TP 触发收缩,但 hardware_family 无显存后缀 → CLI 友好报错(前置闸,exit 2,无 traceback)。"""
    hardware_info = tmp_path / "hw.json"
    # ascend-a3 无 _<N>G 后缀 → 拿不到单卡显存 → 收缩前置闸友好报错。
    hardware_info.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl", "--engine", "vllm-ascend", "--model-name", "DeepSeek-V4-Flash",
            "--config-root", str(config_root_real), "--hardware-info", str(hardware_info),
            "--device-count", "2", "--dry-run",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    # cnt<TP → 收缩前置闸;此 fixture hardware_family 无 _<N>G 后缀 → 拿不到显存 → 友好报错。
    assert "gpu_mem" in capsys.readouterr().err


def _shrink_argv(tmp_path, config_root_real, *, gpu_mem, total_size_gb, heads=32, device_count=2):
    """构造 R-H 收缩 e2e 的 argv:造权重目录(index/config)+ 带 gpu_mem 的 hw.json,dry-run。"""
    weights = tmp_path / "weights"
    weights.mkdir()
    (weights / "model.safetensors.index.json").write_text(
        json.dumps({"metadata": {"total_size": total_size_gb * 2**30}}), encoding="utf-8"
    )
    (weights / "config.json").write_text(
        json.dumps({"num_attention_heads": heads}), encoding="utf-8"
    )
    # 单卡显存放进 hardware_family 的 _<N>G 后缀(唯一来源);strip 后回落 ascend-a3 目录。
    hw = tmp_path / "hw.json"
    hw.write_text(
        json.dumps({"hardware_family": f"ascend-a3_{gpu_mem}G", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    return [
        "wings-ctl", "--engine", "vllm-ascend", "--model-name", "DeepSeek-V4-Flash",
        "--model-path", str(weights), "--config-root", str(config_root_real),
        "--hardware-info", str(hw), "--device-count", str(device_count), "--dry-run",
    ]


def test_device_count_shrink_e2e_success(
    config_root_real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """R-H e2e(flash 场景):cnt=2<TP + gpu_mem=64G + 小权重(10G,过闸)→ 收缩,argv 出 TP=2。"""
    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    monkeypatch.setattr("sys.argv", _shrink_argv(tmp_path, config_root_real, gpu_mem=64, total_size_gb=10))
    cli.main()
    out = capsys.readouterr().out
    assert "--tensor-parallel-size 2" in out  # TP 被收缩到 cnt=2


def test_device_count_shrink_e2e_capacity_raise(
    config_root_real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """R-H e2e:cnt=2<TP 但权重过大(300G):2×64=128G < 1.5×300=450G → 显存闸友好 raise(exit 2)。"""
    monkeypatch.setenv("ENGINE_VERSION", "0.18.0")
    monkeypatch.setattr("sys.argv", _shrink_argv(tmp_path, config_root_real, gpu_mem=64, total_size_gb=300))
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "容量不足" in capsys.readouterr().err


def test_builtin_default_host_injected_when_template_and_user_absent(
    config_root_real: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模板无 host + 用户没传 → wings-control 注入 builtin 默认 host=0.0.0.0。

    DeepSeek-V4-Flash standalone 模板有 port=8008(覆盖 builtin)、无 host。
    """
    argv, audit = _run_cli(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        config_root_real=config_root_real,
        engine="vllm-ascend",
        model="DeepSeek-V4-Flash",
        hw_dict={"hardware_family": "ascend-a3", "device": "ascend", "count": 16},
        engine_version="0.18.0",
        cli_args=[],  # 故意不传 --host/--port;--model-name 由 _run_cli 提供
    )
    # host:模板/用户都没给 → builtin 兜底
    host_trace = audit["engine_config"]["host"]
    assert host_trace["final_value"] == "0.0.0.0"
    assert host_trace["final_layer"] == "builtin_default"
    assert "--host 0.0.0.0" in argv
    # port:模板有 8008 → 覆盖 builtin(17000),final_layer 非 builtin
    port_trace = audit["engine_config"]["port"]
    assert port_trace["final_value"] == 8008
    assert port_trace["final_layer"] == "model_scenario"

