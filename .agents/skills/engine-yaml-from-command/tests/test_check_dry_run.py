from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check_dry_run.py"
spec = importlib.util.spec_from_file_location("check_dry_run", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_case(tmp_path: Path, *, feature_args: str, command_args: str = "") -> tuple[Path, Path]:
    yaml_path = tmp_path / "model.yaml"
    command_path = tmp_path / "start.sh"
    yaml_path.write_text(
        """upstream_sources: []
model:
  name: Demo
  provider: Demo
  model_id: demo/model
  min_engine_version: v0.1.0
  match: [{name_pattern: demo}]
  variant_name: Demo
hardware_profile: {gpu_count: 1, vram_gb: 80, multi_node: false}
features:
  tool_calling:
    args: [--enable-auto-tool-choice, --tool-call-parser, hermes]
  reasoning:
    args: [--reasoning-parser, deepseek]
scenarios:
  standalone:
    match: {distributed: false}
    strategies:
      single:
        default_strategy: true
        engine_config:
          model: demo/model
          tensor_parallel_size: 1
""".replace(
            "  tool_calling:\n    args: [--enable-auto-tool-choice, --tool-call-parser, hermes]\n  reasoning:\n    args: [--reasoning-parser, deepseek]",
            feature_args,
        ),
        encoding="utf-8",
    )
    command_path.write_text(
        "vllm serve demo/model --tensor-parallel-size 1 " + command_args + "\n",
        encoding="utf-8",
    )
    return yaml_path, command_path


def test_tool_calling_and_reasoning_are_included_in_dry_run(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(
        tmp_path,
        feature_args="""  tool_calling:
    args: [--enable-auto-tool-choice, --tool-call-parser, hermes]
  reasoning:
    args: [--reasoning-parser, deepseek]""",
        command_args="--enable-auto-tool-choice --tool-call-parser hermes --reasoning-parser deepseek",
    )
    report = module.check(yaml_path, [command_path], "vllm", "standalone")
    output = "\\n".join(report)
    assert "YAML 重建命令" in output
    assert "原始启动命令" in output
    assert "node[0]: OK" in output
    assert "OK       --reasoning-parser" in output


def test_environment_matches_explicit_exports(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(
        tmp_path,
        feature_args="""  tool_calling:
    args: [--enable-auto-tool-choice]
  reasoning:
    args: [--reasoning-parser, deepseek]""",
        command_args="--enable-auto-tool-choice --reasoning-parser deepseek",
    )
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(yaml_text.replace("          tensor_parallel_size: 1\n", "          tensor_parallel_size: 1\n          env: {NCCL_P2P_LEVEL: SYS, NCCL_SHM_DISABLE: 1}\n"), encoding="utf-8")
    command_path.write_text(
        "export NCCL_P2P_LEVEL=SYS\nexport NCCL_SHM_DISABLE=1\n"
        + command_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    report = module.check(yaml_path, [command_path], "vllm", "standalone")
    assert "node[0] env: OK" in "\n".join(report)


def test_environment_mismatch_fails(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(tmp_path, feature_args="", command_args="")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(yaml_text.replace("          tensor_parallel_size: 1\n", "          tensor_parallel_size: 1\n          env: {NCCL_P2P_LEVEL: SYS}\n"), encoding="utf-8")
    try:
        module.check(yaml_path, [command_path], "vllm", "standalone")
    except module.DryRunMismatch as exc:
        assert "NCCL_P2P_LEVEL" in str(exc)
        assert "缺失" in str(exc)
    else:
        raise AssertionError("missing environment export was accepted")


def test_missing_reasoning_parameter_fails(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(
        tmp_path,
        feature_args="""  tool_calling:
    args: [--enable-auto-tool-choice, --tool-call-parser, hermes]
  reasoning:
    args: [--reasoning-parser, deepseek]""",
        command_args="--enable-auto-tool-choice --tool-call-parser hermes",
    )
    try:
        module.check(yaml_path, [command_path], "vllm", "standalone")
    except module.DryRunMismatch as exc:
        assert "--reasoning-parser" in str(exc)
    else:
        raise AssertionError("missing reasoning flag was accepted")


def test_nested_vllm_config_preserves_nested_underscores_and_bool_case(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(tmp_path, feature_args="", command_args="")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(
        yaml_text.replace(
            "          tensor_parallel_size: 1\n",
            "          tensor_parallel_size: 1\n"
            "          cc.pass_config.fuse_allreduce_rms: false\n",
        ),
        encoding="utf-8",
    )
    command_path.write_text(
        "vllm serve demo/model --tensor-parallel-size 1 "
        "--cc.pass_config.fuse_allreduce_rms=False\n",
        encoding="utf-8",
    )

    report = module.check(yaml_path, [command_path], "vllm", "standalone")

    assert "--cc.pass_config.fuse_allreduce_rms=false" in "\n".join(report)


def test_numeric_feature_argument_matches_command(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(
        tmp_path,
        feature_args="""  kv_offloading:
    args: [--kv-offloading-backend, native, --kv-offloading-size, 200]""",
        command_args="--kv-offloading-backend native --kv-offloading-size 200",
    )

    report = module.check(yaml_path, [command_path], "vllm", "standalone")

    assert "--kv-offloading-size" in "\n".join(report)


def test_standalone_host_is_normalized_when_omitted_from_command(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(tmp_path, feature_args="", command_args="")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(
        yaml_text.replace(
            "          tensor_parallel_size: 1\n",
            "          host: 0.0.0.0\n"
            "          tensor_parallel_size: 1\n",
        ),
        encoding="utf-8",
    )

    report = module.check(yaml_path, [command_path], "vllm", "standalone")

    assert "node[0]: OK" in "\n".join(report)


def test_standalone_host_is_normalized_when_command_differs(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(tmp_path, feature_args="", command_args="")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(
        yaml_text.replace(
            "          tensor_parallel_size: 1\n",
            "          host: 0.0.0.0\n"
            "          tensor_parallel_size: 1\n",
        ),
        encoding="utf-8",
    )
    command_path.write_text(
        "vllm serve demo/model --host 127.0.0.1 --tensor-parallel-size 1\n",
        encoding="utf-8",
    )

    report = module.check(yaml_path, [command_path], "vllm", "standalone")

    assert "node[0]: OK" in "\n".join(report)


def test_multi_node_dry_run_matches_head_and_worker(tmp_path: Path) -> None:
    yaml_path = tmp_path / "multi-node.yaml"
    yaml_path.write_text(
        """hardware_profile: {gpu_count: 8, vram_gb: 640, multi_node: true}
features:
  tool_calling:
    args: [--enable-auto-tool-choice, --tool-call-parser, hermes]
scenarios:
  multi_node:
    strategies:
      head_worker:
        default_strategy: true
        head:
          engine_config:
            model: demo/model
            tensor_parallel_size: 8
            pipeline_parallel_size: 2
            master_addr: 10.0.0.1
            master_port: 29500
        worker:
          engine_config:
            model: demo/model
            tensor_parallel_size: 8
            pipeline_parallel_size: 2
            master_addr: 10.0.0.1
            master_port: 29500
""",
        encoding="utf-8",
    )
    head = tmp_path / "head.sh"
    head.write_text(
        "vllm serve demo/model --tensor-parallel-size 8 --pipeline-parallel-size 2 "
        "--master-addr 10.0.0.1 --master-port 29500 "
        "--enable-auto-tool-choice --tool-call-parser hermes\n",
        encoding="utf-8",
    )
    worker = tmp_path / "worker.sh"
    worker.write_text(
        "vllm serve demo/model --tensor-parallel-size 8 --pipeline-parallel-size 2 "
        "--master-addr 10.0.0.1 --master-port 29500 "
        "--enable-auto-tool-choice --tool-call-parser hermes\n",
        encoding="utf-8",
    )

    report = module.check(yaml_path, [head, worker], "vllm", "multi_node")
    output = "\\n".join(report)
    assert "node[0]: OK" in output
    assert "node[1]: OK" in output
    assert "--master-addr" in output


def test_multi_node_dry_run_rejects_node_count_mismatch(tmp_path: Path) -> None:
    yaml_path = tmp_path / "multi-node.yaml"
    yaml_path.write_text(
        """hardware_profile: {gpu_count: 8, vram_gb: 640, multi_node: true}
scenarios:
  multi_node:
    strategies:
      head_worker:
        default_strategy: true
        head: {engine_config: {model: demo/model, tensor_parallel_size: 8}}
        worker: {engine_config: {model: demo/model, tensor_parallel_size: 8}}
""",
        encoding="utf-8",
    )
    command = tmp_path / "head.sh"
    command.write_text("vllm serve demo/model --tensor-parallel-size 8\\n", encoding="utf-8")

    try:
        module.check(yaml_path, [command], "vllm", "multi_node")
    except module.DryRunMismatch as exc:
        assert "YAML has 2 engine configs but commands provide 1" in str(exc)
    else:
        raise AssertionError("multi-node command count mismatch was accepted")


def test_pd_disaggregation_dry_run_matches_prefill_and_decode(tmp_path: Path) -> None:
    yaml_path = tmp_path / "pd.yaml"
    yaml_path.write_text(
        """hardware_profile: {gpu_count: 16, vram_gb: 1280, multi_node: true}
features:
  reasoning:
    args: [--reasoning-parser, deepseek]
scenarios:
  pd_disaggregation:
    strategies:
      pd_cluster:
        default_strategy: true
        nodes:
          - role: prefill
            engine_config: {model: demo/model, tensor_parallel_size: 8, data_parallel_size: 1}
          - role: decode
            engine_config: {model: demo/model, tensor_parallel_size: 8, data_parallel_size: 1}
""",
        encoding="utf-8",
    )
    prefill = tmp_path / "prefill.sh"
    prefill.write_text(
        "vllm serve demo/model --tensor-parallel-size 8 --data-parallel-size 1 "
        "--reasoning-parser deepseek\n",
        encoding="utf-8",
    )
    decode = tmp_path / "decode.sh"
    decode.write_text(
        "vllm serve demo/model --tensor-parallel-size 8 --data-parallel-size 1 "
        "--reasoning-parser deepseek\n",
        encoding="utf-8",
    )

    report = module.check(yaml_path, [prefill, decode], "vllm", "pd_disaggregation")
    output = "\\n".join(report)
    assert "node[0]: OK" in output
    assert "node[1]: OK" in output


def test_command_tokens_parses_quoted_multiline_json() -> None:
    tokens = module.command_tokens(
        """export HCCL_BUFFSIZE=400
vllm serve demo/model \\
  --kv-transfer-config \\
  '{"kv_connector": "MooncakeConnectorV1",
    "kv_connector_extra_config": {"use_ascend_direct": true}}'
"""
    )

    assert tokens == [
        "vllm",
        "serve",
        "demo/model",
        "--kv-transfer-config",
        '{"kv_connector": "MooncakeConnectorV1",\n    "kv_connector_extra_config": {"use_ascend_direct": true}}',
    ]


def test_command_tokens_strips_line_continuation_whitespace() -> None:
    tokens = module.command_tokens(
        "vllm serve demo/model \\\n--tensor-parallel-size 8 \\\n--enable-expert-parallel\n"
    )

    assert tokens == [
        "vllm",
        "serve",
        "demo/model",
        "--tensor-parallel-size",
        "8",
        "--enable-expert-parallel",
    ]


def test_command_env_ignores_ascend_visible_devices() -> None:
    assert module.command_env(
        "export ASCEND_RT_VISIBLE_DEVICES=$1\nexport HCCL_BUFFSIZE=256\n"
    ) == {"HCCL_BUFFSIZE": "256"}


def test_default_model_dry_run(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default_model.yaml"
    yaml_path.write_text(
        """hardware:
  gpu_count: 16
  vram_gb: 1024
  multi_node: true
engine:
  name: vllm-ascend
  version: v0.23.0
scenarios:
  standalone:
    strategies:
      single_node:
        default_strategy: true
        engine_config: {tensor_parallel_size: 16}
  multi_node:
    strategies:
      multi_node:
        default_strategy: true
        head: {engine_config: {tensor_parallel_size: 32}}
        worker: {engine_config: {tensor_parallel_size: 32}}
  pd_disaggregation:
    strategies:
      pd_cluster:
        default_strategy: true
        nodes:
          - {role: prefill, engine_config: {tensor_parallel_size: 16}}
          - {role: decode, engine_config: {tensor_parallel_size: 16}}
""",
        encoding="utf-8",
    )
    report = module.check_default_model(yaml_path, "vllm-ascend", "v0.23.0", "ascend910b-x86_64", 16, 64)
    assert "OK: default_model dry-run checks passed" in report[-1]


def test_default_model_dry_run_rejects_wrong_vram(tmp_path: Path) -> None:
    yaml_path = tmp_path / "default_model.yaml"
    yaml_path.write_text("hardware: {gpu_count: 16, vram_gb: 512, multi_node: true}\nengine: {name: vllm-ascend, version: v0.23.0}\nscenarios: {}\n", encoding="utf-8")
    try:
        module.check_default_model(yaml_path, "vllm-ascend", "v0.23.0", "ascend910b-x86_64", 16, 64)
    except module.DryRunMismatch as exc:
        assert "hardware.vram_gb" in str(exc)
    else:
        raise AssertionError("wrong vram was accepted")


def test_feature_value_mismatch_fails(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(
        tmp_path,
        feature_args="""  tool_calling:
    args: [--enable-auto-tool-choice, --tool-call-parser, hermes]
  reasoning:
    args: [--reasoning-parser, deepseek]""",
        command_args="--enable-auto-tool-choice --tool-call-parser other --reasoning-parser deepseek",
    )
    try:
        module.check(yaml_path, [command_path], "vllm", "standalone")
    except module.DryRunMismatch as exc:
        message = str(exc)
        assert "--tool-call-parser" in message
        assert "YAML='hermes'" in message
        assert "command='other'" in message
    else:
        raise AssertionError("feature value mismatch was accepted")
