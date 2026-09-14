from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


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
    assert "OK       --tool-call-parser" in output
    assert "OK       --reasoning-parser" in output


def test_chat_template_requires_user_command_source(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(
        tmp_path,
        feature_args="""  tool_calling:
    args: [--enable-auto-tool-choice, --tool-call-parser, deepseek_v3, --chat-template, examples/tool_chat_template_deepseekv3.jinja]
  reasoning:
    args: [--reasoning-parser, deepseek]""",
        command_args="--enable-auto-tool-choice --tool-call-parser deepseek_v3 --reasoning-parser deepseek",
    )

    try:
        module.check(yaml_path, [command_path], "vllm", "standalone")
    except module.DryRunMismatch as exc:
        assert "must originate from the user command" in str(exc)
    else:
        raise AssertionError("YAML-only chat template was accepted")


def test_chat_template_matches_explicit_user_command(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(
        tmp_path,
        feature_args="""  tool_calling:
    args: [--enable-auto-tool-choice, --tool-call-parser, deepseek_v3, --chat-template, examples/tool_chat_template_deepseekv3.jinja]
  reasoning:
    args: [--reasoning-parser, deepseek]""",
        command_args="--enable-auto-tool-choice --tool-call-parser deepseek_v3 --chat-template examples/tool_chat_template_deepseekv3.jinja --reasoning-parser deepseek",
    )

    report = module.check(yaml_path, [command_path], "vllm", "standalone")

    assert "OK       --chat-template" in "\n".join(report)


def test_vllm_served_model_name_is_ignored_as_a_deployment_local_alias(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(
        tmp_path,
        feature_args="",
        command_args="--served-model-name local-demo",
    )

    report = module.check(yaml_path, [command_path], "vllm", "standalone")

    assert "node[0]: OK" in "\n".join(report)


def test_vllm_dry_run_accepts_underscore_parameter_aliases(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(
        tmp_path,
        feature_args="",
        command_args="--max_model_len 200000",
    )
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(
        yaml_text.replace("          tensor_parallel_size: 1\n", "          tensor_parallel_size: 1\n          max_model_len: 200000\n"),
        encoding="utf-8",
    )

    report = module.check(yaml_path, [command_path], "vllm", "standalone")

    assert "node[0]: OK" in "\n".join(report)


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


def test_source_commands_match_in_order(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(tmp_path, feature_args="", command_args="")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(
        yaml_text.replace(
            "          tensor_parallel_size: 1\n",
            "          tensor_parallel_size: 1\n"
            "        system_setup:\n"
            "          commands: [source /usr/local/Ascend/ascend-toolkit/set_env.sh, "
            "source /usr/local/Ascend/nnal/atb/set_env.sh]\n",
        ),
        encoding="utf-8",
    )
    command_path.write_text(
        "source /usr/local/Ascend/ascend-toolkit/set_env.sh\n"
        "source /usr/local/Ascend/nnal/atb/set_env.sh\n"
        "vllm serve demo/model --tensor-parallel-size 1\n",
        encoding="utf-8",
    )

    report = module.check(yaml_path, [command_path], "vllm-ascend", "standalone")

    assert "node[0] source commands: OK" in "\n".join(report)


def test_source_command_order_mismatch_fails(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(tmp_path, feature_args="", command_args="")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(
        yaml_text.replace(
            "          tensor_parallel_size: 1\n",
            "          tensor_parallel_size: 1\n"
            "        system_setup:\n"
            "          commands: [source /usr/local/Ascend/ascend-toolkit/set_env.sh]\n",
        ),
        encoding="utf-8",
    )
    command_path.write_text(
        "source /usr/local/Ascend/nnal/atb/set_env.sh\n"
        "vllm serve demo/model --tensor-parallel-size 1\n",
        encoding="utf-8",
    )

    try:
        module.check(yaml_path, [command_path], "vllm-ascend", "standalone")
    except module.DryRunMismatch as exc:
        assert "source[0]" in str(exc)
    else:
        raise AssertionError("source command mismatch was accepted")


def test_relative_source_command_fails(tmp_path: Path) -> None:
    yaml_path, command_path = write_case(tmp_path, feature_args="", command_args="")
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(
        yaml_text.replace(
            "          tensor_parallel_size: 1\n",
            "          tensor_parallel_size: 1\n"
            "        system_setup:\n"
            "          commands: [source relative/set_env.sh]\n",
        ),
        encoding="utf-8",
    )
    command_path.write_text(
        "source relative/set_env.sh\n"
        "vllm serve demo/model --tensor-parallel-size 1\n",
        encoding="utf-8",
    )

    with pytest.raises(module.DryRunMismatch, match="source <absolute-path>"):
        module.check(yaml_path, [command_path], "vllm-ascend", "standalone")


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
            "          kernel_config.enable_flashinfer_autotune: false\n",
        ),
        encoding="utf-8",
    )
    command_path.write_text(
        "vllm serve demo/model --tensor-parallel-size 1 "
        "--kernel-config.enable_flashinfer_autotune=False\n",
        encoding="utf-8",
    )

    report = module.check(yaml_path, [command_path], "vllm", "standalone")

    assert "--kernel-config.enable_flashinfer_autotune=false" in "\n".join(report)


def test_cc_pass_config_single_dash_special_case_is_rendered_and_matches(tmp_path: Path) -> None:
    """vLLM ``cc.*``(pass 配置)渲成单横线 ``-cc.xxx=value``;值为 false 也显式输出并匹配命令。"""
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
        "-cc.pass_config.fuse_allreduce_rms=False\n",
        encoding="utf-8",
    )

    report = module.check(yaml_path, [command_path], "vllm", "standalone")
    output = "\n".join(report)

    assert "node[0]: OK" in output
    assert "-cc.pass_config.fuse_allreduce_rms=false" in output


def test_cc_single_dash_flag_is_not_eaten_as_previous_flag_value(tmp_path: Path) -> None:
    """裸 flag 后紧跟 ``-cc.xxx=value`` 时,后者仍是独立 flag,不被当作前者的值。"""
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
        "--trust-remote-code -cc.pass_config.fuse_allreduce_rms=False\n",
        encoding="utf-8",
    )

    parsed = module.parse_tokens(
        module.command_tokens(command_path.read_text(encoding="utf-8")), "vllm"
    )

    assert parsed["--trust-remote-code"] == "true"
    assert parsed["-cc.pass_config.fuse_allreduce_rms"] == "False"


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


def test_sglang_multi_node_host_is_normalized_when_command_differs(tmp_path: Path) -> None:
    yaml_path = tmp_path / "multi-node.yaml"
    yaml_path.write_text(
        """hardware_profile: {gpu_count: 8, vram_gb: 640, multi_node: true}
scenarios:
  multi_node:
    strategies:
      head_worker:
        default_strategy: true
        head:
          engine_config: {model: demo/model, host: 0.0.0.0, tp_size: 8}
        worker:
          engine_config: {model: demo/model, host: 0.0.0.0, tp_size: 8}
""",
        encoding="utf-8",
    )
    head = tmp_path / "head.sh"
    worker = tmp_path / "worker.sh"
    head.write_text("python3 -m sglang.launch_server --model demo/model --host 10.0.0.1 --tp-size 8\n", encoding="utf-8")
    worker.write_text("python3 -m sglang.launch_server --model demo/model --host 10.0.0.2 --tp-size 8\n", encoding="utf-8")

    report = module.check(yaml_path, [head, worker], "sglang", "multi_node")

    assert "node[0]: OK" in "\n".join(report)
    assert "node[1]: OK" in "\n".join(report)


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


def test_sglang_tp_alias_is_equivalent_to_tp_size() -> None:
    expected = {"--tp-size": "8"}
    actual = {"--tp": "8"}

    assert module.compare(expected, actual, "node[0]", "sglang") == ["node[0]: OK", "  OK       --tp-size: '8'"]


def test_rtx_pro_5000_auto_environment_is_ignored_for_dry_run() -> None:
    expected = {
        "GLOO_SOCKET_IFNAME": "bond0",
        "NCCL_P2P_LEVEL": "SYS",
        "NCCL_SHM_DISABLE": "1",
    }
    actual = {"GLOO_SOCKET_IFNAME": "bond0"}

    assert module.compare_environment(
        expected,
        actual,
        "node[0]",
        module.RTX_PRO_5000_AUTO_ENV_VARS,
    ) == ["node[0] env: OK", "  OK       GLOO_SOCKET_IFNAME: 'bond0'"]


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
