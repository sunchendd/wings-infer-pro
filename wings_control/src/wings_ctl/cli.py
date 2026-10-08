"""wings_ctl CLI — trace-first 配置解析可执行入口。

职责:解析 CLI/env → 收集用户具名参数(user_cli 覆盖层)→ 大策略层推导 topology → 调 pipeline。
不负责:参数合并/翻译、脚本渲染、落盘 —— 分别归 core/config_resolver、translators、pipeline/rendering。

用法:
    python -m wings_ctl --model-name Qwen3.5-0.8B --hardware-info hardware_info.json
    python -m wings_ctl --model-name kimi-k2.5 --engine vllm-ascend \\
        --hardware-info hw.json --host 0.0.0.0 \\
        --model-path /weights/custom-model
    python -m wings_ctl --help

定位参数 (驱动配置查找):
    --model-name      模型名称, 用于 name_pattern 匹配(亦作 served_model_name);
                      缺省时从 --model-path basename 推导
    --hardware-info   hardware_info.json 路径 (可选; 不传则读固定目录 /shared-volume/hardware_info.json)
    --engine          引擎名称 (fallback: ENGINE env, 默认 vllm)
    --distributed     分布式判定总开关; topology 由大策略层从此+PD_ROLE/NODE_IPS/MASTER_IP 推导
    --config-root     配置资产根目录 (默认 auto-detect)

用户覆盖层 (选填, 进入 user_cli 合并层, 优先级最高):
    --host / --port / --model-path / --model-name / --max-num-seqs / ...

输出:
    --output-dir / -o  脚本和 audit 输出目录 (默认: 存在 /shared-volume 则用之, 否则 cwd)
    --dry-run          仅打印 argv, 不写文件
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
from pathlib import Path
from typing import Any, Dict, List

from wings_ctl.common.log_config import LOGGER_LAUNCHER, setup_root_logging
from wings_ctl.core.config_resolver import DEFAULT_ENGINE_PORT
from wings_ctl.core.models import ClusterPlacement, CustomConfigFile, PipelineRequest, Target, UserInput
from wings_ctl.core.system_setup import render_source_command_blocks
from wings_ctl.engines.registry import format_launch_dry_run_preview, format_launch_summary
from wings_ctl.engines.vllm_adapter import build_argv, build_system_setup_source_commands
from wings_ctl.license_gate import validate_device_count_early
from wings_ctl.pd.input_contract import parse_pd_runtime_input
from wings_ctl.pipeline import resolve_pipeline, resolve_pipeline_custom, run_pipeline, run_pipeline_custom
from wings_ctl.rendering.env_renderer import render_env_export
from wings_ctl.strategy.pre_template import pre_template_strategy
from wings_ctl.translators.cli_translator import CLITranslator
from wings_ctl.utils.env_utils import is_mooncake_master_pod, parse_node_ips


logger = logging.getLogger(LOGGER_LAUNCHER)


def _collect_user_cli_overrides(
    host: str | None,
    port: int | None,
    model_path: str | None,
    engine_port: int | None = None,
    model_name: str | None = None,
    served_model_name: str | None = None,
    max_num_seqs: int | None = None,
    max_num_batched_tokens: int | None = None,
    input_length: int | None = None,
    output_length: int | None = None,
    trust_remote_code: bool | None = None,
    enable_auto_think_choice: bool | None = None,
    enable_auto_tool_choice: bool | None = None,
    dtype: str | None = None,
    kv_cache_dtype: str | None = None,
    quantization: str | None = None,
    quantization_param_path: str | None = None,
    gpu_memory_utilization: float | None = None,
    block_size: int | None = None,
    seed: int | None = None,
    enable_chunked_prefill: bool | None = None,
    enable_prefix_caching: bool | None = None,
    enable_expert_parallel: bool | None = None,
    enable_smartqos: bool | None = None,
    enable_otlp_traces: bool | None = None,
    enable_metrics: bool | None = None,
) -> Dict[str, Any]:
    """收集用户 CLI 覆盖层 dict。

    来源: 具名参数/语法糖.
    Returns:
        overrides dict, key 为 engine_config 的 canonical 参数名.
        传给 resolve_config(..., user_cli_overrides=overrides) 作为最高优先级合并层.

    端口转换:用户传的 --port 是 proxy 对外端口;引擎应监听 backend 端口(ENGINE_PORT/默认 17000)。
    本函数**只读 env、不写 env**;proxy 端口写 env 的副作用在 main 中显式调用。
    """
    overrides: Dict[str, Any] = {}
    if host is not None:
        overrides["host"] = host
    if engine_port is not None:
        # --engine-port 是 engine backend 端口的显式覆盖,优先级高于 ENGINE_PORT env;
        # 它与 --port(仅 proxy)无关,直接作为 engine `port` 进入 user_cli 层。
        overrides["port"] = engine_port
    elif port is not None or os.environ.get("ENGINE_PORT"):
        # --port 有**两个去向**(别当 bug):用户 --port 是 **proxy 对外端口**,不是引擎端口。
        #   ① 这里:engine 的 `port` 覆盖成 **backend 端口**(ENGINE_PORT / 默认 17000),它才进 argv。
        #   ② 另一处:**proxy 对外端口**由 _export_proxy_port() 写入 env PORT(见该函数)。
        # 所以用户传的端口值本身不进 argv,进 argv 的是 backend 端口。
        backend_port = int(os.environ.get("ENGINE_PORT", str(DEFAULT_ENGINE_PORT)))
        overrides["port"] = backend_port
    if model_path is not None:
        overrides["model_path"] = model_path
    if model_name is not None:
        overrides["model_name"] = model_name
    if served_model_name is not None:
        overrides["served_model_name"] = served_model_name
    if max_num_seqs is not None:
        overrides["max_num_seqs"] = max_num_seqs
    if max_num_batched_tokens is not None:
        # 同名直通,由 user_cli 层覆盖 recipe。
        overrides["max_num_batched_tokens"] = max_num_batched_tokens
    if input_length is not None:
        overrides["input_length"] = input_length
    if output_length is not None:
        overrides["output_length"] = output_length
    # 显式派生 max_model_len = input + output;input/output 原值不直接进 argv。
    derived_mml = _derive_max_model_len(input_length, output_length)
    if derived_mml is not None:
        overrides["max_model_len"] = derived_mml
    if trust_remote_code is not None:
        overrides["trust_remote_code"] = trust_remote_code
    if enable_auto_think_choice is not None:
        overrides["enable_auto_think_choice"] = enable_auto_think_choice
    if enable_auto_tool_choice is not None:
        overrides["enable_auto_tool_choice"] = enable_auto_tool_choice
    if dtype is not None:
        overrides["dtype"] = dtype
    if kv_cache_dtype is not None:
        overrides["kv_cache_dtype"] = kv_cache_dtype
    if quantization is not None:
        overrides["quantization"] = quantization
    if quantization_param_path is not None:
        overrides["quantization_param_path"] = quantization_param_path
    if gpu_memory_utilization is not None:
        overrides["gpu_memory_utilization"] = gpu_memory_utilization
    if block_size is not None:
        overrides["block_size"] = block_size
    if seed is not None:
        overrides["seed"] = seed
    if enable_chunked_prefill is not None:
        overrides["enable_chunked_prefill"] = enable_chunked_prefill
    if enable_prefix_caching is not None:
        overrides["enable_prefix_caching"] = enable_prefix_caching
    if enable_expert_parallel is not None:
        overrides["enable_expert_parallel"] = enable_expert_parallel
    if enable_smartqos is not None:
        overrides["enable_smartqos"] = enable_smartqos
    if enable_otlp_traces is not None:
        overrides["enable_otlp_traces"] = enable_otlp_traces
    if enable_metrics is not None:
        overrides["enable_metrics"] = enable_metrics

    return overrides


def _export_proxy_port(port: int | None) -> None:
    """把用户 ``--port``(对外/代理端口)写入 ``os.environ["PORT"]``,供 proxy 子系统读取。

    ⚠️ **有意的全局副作用**(sidecar 接缝:cli → env → proxy):独立成函数、由 main 显式调用。
    引擎 backend 端口**不走这里**(见 ``_collect_user_cli_overrides`` / ENGINE_PORT)。

    Args:
        port: ``--port`` 值;None 时不写(保持 env 原样)。
    """
    if port is not None:
        os.environ["PORT"] = str(port)


def _drop_pd_backend_port_compat(
    overrides: Dict[str, Any],
    dropped: list[Dict[str, Any]],
) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    """移除 ``--port``/``--engine-port`` 在 PD 下派生的 user_cli ``port`` 覆盖。

    PD backend 端口由 exact recipe 规划,并可通过 ``--engine-port``/``ENGINE_PORT``
    作为端口基座覆盖(由 resolver 侧 UserInput.engine_port/ambient env 承载),
    不能再经 user_cli 层二次改写。这里去掉该派生值并保留 dropped audit;
    ``--port`` 的 proxy 语义已由 ``_export_proxy_port`` 写入 ``PORT``。
    """
    if "port" not in overrides:
        return overrides, dropped
    filtered = dict(overrides)
    value = filtered.pop("port")
    dropped_with_pd = list(dropped)
    dropped_with_pd.append(
        {
            "key": "port",
            "value": value,
            "reason": (
                "PD engine backend port base comes from --engine-port/ENGINE_PORT and the exact recipe; "
                "--port remains proxy PORT"
            ),
        }
    )
    return filtered, dropped_with_pd


def _export_smartqos_env(enable_smartqos: bool | None) -> None:
    """把 ``--enable-smartqos`` 写入 ``os.environ["ENABLE_SMARTQOS"]``,供 proxy 子进程继承。

    ENABLE_SMARTQOS 需要被 proxy 子进程消费（Anthropic 协议转换门控）。
    在 ``main()`` 中调用后,``wings_control._build_child_env()``
    通过 ``os.environ.copy()`` 自动继承,无需额外修改。

    Args:
        enable_smartqos: ``--enable-smartqos`` 值;None/False 时不写(保持 env 原样)。
    """
    if enable_smartqos:
        os.environ["ENABLE_SMARTQOS"] = "true"


def _export_rag_acc_env(enable_rag_acc: bool | None) -> None:
    """Export the authoritative CLI RAG switch for the proxy child process."""
    os.environ["RAG_ACC_ENABLED"] = "true" if enable_rag_acc is True else "false"


def _canonicalize_engine(name: str) -> str:
    """归一引擎名到 config 目录命名(连字符)。

    MaaS/部署可能下发下划线形式(如 ``vllm_ascend``,对齐 wings-accel schema 命名),
    而 wings-control 配置目录用连字符(``config/engines/vllm-ascend``)。统一把 ``_`` 归一为
    ``-``,使两种写法都能定位到同一资产。该归一规则对所有引擎一致生效。

    Args:
        name: 原始引擎名(可能含下划线 / 首尾空白)。

    Returns:
        归一后的引擎名(去空白、``_``→``-``)。
    """
    return name.strip().replace("_", "-")


def _derive_max_model_len(input_length: int | None, output_length: int | None) -> int | None:
    """由 input/output 长度显式派生 max_model_len(= 总上下文窗口)。

    ``max_model_len = input_length + output_length``(prompt 上限 + 生成上限 = 模型总序列长度),不加余量。
    产出作为 user_cli 覆盖层的 ``max_model_len``,**覆盖 recipe 自带值**(用户必填值优先)。

    embedding/rerank 等 pooling 模型没有输出生成侧,MaaS 不下发 output_length:
    此时缺失侧按 0 处理,``max_model_len = input_length``(与 legacy JSON 路径语义一致)。

    Args:
        input_length: 输入序列最大长度(MaaS 必填;None=未传)。
        output_length: 输出序列最大长度(生成模型必填;缺失/非正按 0 处理)。

    Returns:
        ``input_length + output_length``;input 缺失或非正 → None(不派生,不覆盖 recipe)。
    """
    if input_length is None or input_length <= 0:
        logger.warning("input_length=%s; skip max_model_len derivation", input_length)
        return None
    mml = input_length + max(output_length or 0, 0)
    logger.info("max_model_len = %d + %s = %d", input_length, output_length, mml)
    return mml


def _resolve_engine(cli_engine: str | None) -> str:
    """解析引擎名称。优先级: CLI --engine > ENGINE env > "vllm";统一归一连字符。"""
    if cli_engine is not None:
        return _canonicalize_engine(cli_engine)
    env_engine = os.environ.get("ENGINE", "").strip()
    if env_engine:
        return _canonicalize_engine(env_engine)
    return "vllm"


# sidecar 共享卷:wings-control 与 engine 容器通过该目录交换文件。
# hardware_info.json 从此读入,start_command.sh/repro.sh/audit.json 默认写回这里。
SHARED_VOLUME_DIR = Path("/shared-volume")
# 硬件信息默认路径:wings-engine 探测后写入共享卷,wings-control 只读该文件。
# MaaS/sidecar 部署下该文件通常固定在此,因此 --hardware-info 可省略。
DEFAULT_HARDWARE_INFO_PATH = SHARED_VOLUME_DIR / "hardware_info.json"


def _resolve_output_dir(cli_value: Path | None) -> Path:
    """解析三件产物(start_command.sh / repro.sh / audit.json)输出目录。

    优先级:``--output-dir``(CLI)> 共享卷 ``/shared-volume``(**存在则用**)> 当前目录 ``.``。
    sidecar 部署下 engine 容器从共享卷读 ``start_command.sh``,故默认产物落共享卷,
    免得还要显式传 ``--output-dir``;非 sidecar(本地/CI,无该卷)回退 cwd,行为不变。

    Args:
        cli_value: ``--output-dir`` 传入值;None 表示未传。

    Returns:
        实际输出目录。
    """
    if cli_value is not None:
        return cli_value
    if SHARED_VOLUME_DIR.is_dir():
        logger.info("--output-dir was not provided; using shared volume %s for generated artifacts", SHARED_VOLUME_DIR)
        return SHARED_VOLUME_DIR
    return Path(".")


def _resolve_hardware_info_path(cli_path: Path | None) -> Path:
    """解析 hardware_info.json 路径(``--hardware-info`` 为**可选**参数)。

    **仅两条途径**:① ``--hardware-info``(CLI 可选)② 不传则读固定目录
    ``/shared-volume/hardware_info.json``。硬件信息由 wings-engine 探测写入共享卷、框架只读。
    本函数只做**路径选择**,不校验文件是否存在;
    缺失/不可读会在 ``resolve_hardware`` 阶段明确报错。

    Args:
        cli_path: ``--hardware-info`` 传入的路径;None 表示未传。

    Returns:
        ``cli_path`` 或默认共享卷路径。
    """
    if cli_path is not None:
        return cli_path
    logger.info(
        "--hardware-info was not provided; using default hardware discovery output %s",
        DEFAULT_HARDWARE_INFO_PATH,
    )
    return DEFAULT_HARDWARE_INFO_PATH


def _resolve_device_count(cli_value: int | None) -> int | None:
    """解析 device-count。优先级: CLI --device-count > DEVICE_COUNT env > None(未提供)。

    非 None 时驱动小策略层 DeviceCountTransform 协调 DP(``DP = cnt // TP``,TP 静态,并写 trace)。
    缺省返回 None(不触发协调,audit 记 'unset')。
    """
    if cli_value is not None:
        return cli_value
    env_val = os.environ.get("DEVICE_COUNT", "").strip()
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            logger.warning("DEVICE_COUNT environment value '%s' is not an integer; treating it as unset", env_val)
            return None
    return None


def _apply_gpu_usage_mode(
    user_cli_overrides: Dict[str, Any],
    gpu_usage_mode: str | None,
    engine: str,
) -> Dict[str, Any]:
    """把 GPU 使用模式转换为引擎原生参数覆盖。

    ``enpu`` 模式配合 vLLM-Ascend 时向最高优先级 ``user_cli``
    层注入 ``enforce_eager=True``，最终由 argv 渲染器输出 ``--enforce-eager``。
    其他引擎或模式保持原配置。

    Args:
        user_cli_overrides: 已完成 MaaS 契约过滤和引擎参数翻译的覆盖层。
        gpu_usage_mode: ``--gpu-usage-mode`` 原始值。
        engine: 已归一化的引擎名。

    Returns:
        新的 user_cli 覆盖层；不会原地修改入参。
    """
    result = dict(user_cli_overrides)
    if (gpu_usage_mode or "").strip().casefold() != "enpu":
        return result
    if engine != "vllm-ascend":
        return result

    result["enforce_eager"] = True
    logger.info("gpu-usage-mode=enpu: injecting --enforce-eager")
    return result


def _resolve_model_name(model_name: str | None, model_path: str | None) -> str:
    """推导配方查找用的模型标识(name_pattern 匹配)。

    优先级:``--model-name``(模型名称)> ``--model-path`` 的 basename。
    `--model` 已删除(冗余):直接用 ``--model-name`` 做
    ``model.match[].name_pattern`` 匹配,同时它也作 ``served_model_name``。缺 ``--model-name``
    时退而取 ``--model-path`` 目录名(如 ``/…/MiniMax-M3-MXFP8`` → ``MiniMax-M3-MXFP8``)。

    Args:
        model_name: ``--model-name``(模型名称)。
        model_path: ``--model-path``(模型路径;model_name 缺省时取其 basename)。

    Returns:
        用于 name_pattern 匹配的模型名。

    Raises:
        ValueError: ``--model-name`` 与 ``--model-path`` 都缺,无法确定配方标识。
    """
    if model_name:
        return model_name
    if model_path:
        name = Path(model_path).name  # basename;应匹配 recipe 的 name_pattern
        logger.info("--model-name was not provided; derived recipe identifier from --model-path: %s", name)
        return name
    raise ValueError("Either --model-name or --model-path is required to identify the recipe")


def _collect_subsystem_switches(args: argparse.Namespace) -> List[str]:
    """提取已开启的子系统开关(用于启动日志留痕)。

    注意:本函数仅做日志留痕,不决定开关的消费方式。
    - enable_rag_acc:由 proxy/RAG 子系统消费,不进引擎 argv。
    - enable_smartqos / enable_otlp_traces / enable_metrics:
      进入 feature_switches,由 feature_inject 注入 engine_config/env。
    各开关的实际消费在 main() 中由 _collect_user_cli_overrides + feature_switches 完成。

    Args:
        args: argparse 解析结果。

    Returns:
        已开启开关名列表(为空表示未开启)。
    """
    switches = (
        ("enable_rag_acc", args.enable_rag_acc),
        ("enable_smartqos", args.enable_smartqos),
        ("enable_otlp_traces", args.enable_otlp_traces),
        ("enable_metrics", args.enable_metrics),
    )
    return [name for name, enabled in switches if enabled]


def _load_config_file(path: Path) -> CustomConfigFile:
    """加载并校验 config-file JSON,分离 params 和 env。

    结构校验失败(文件缺失 / JSON 语法错误 / 非 dict / params・env 非 dict)→ 友好报错。
    params 的 key 不做字段映射(用户自管),snake_case 归一在 resolve_custom_config 内完成。

    Args:
        path: --config-file 传入的 JSON 文件路径。

    Returns:
        CustomConfigFile(params=..., env=...)。两字段均可选(dict 缺失视为空)。

    Raises:
        ValueError: 文件缺失、JSON 解析失败、或结构非法(供 main 友好报错)。
    """
    if not path.exists():
        raise ValueError(f"config-file does not exist: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse config-file JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"config-file must be a JSON object, got {type(data).__name__} ({path})")
    params = data.get("params", {})
    env = data.get("env", {})
    if not isinstance(params, dict):
        raise ValueError(f"config-file.params must be a JSON object, got {type(params).__name__} ({path})")
    if not isinstance(env, dict):
        raise ValueError(f"config-file.env must be a JSON object, got {type(env).__name__} ({path})")
    return CustomConfigFile(params=dict(params), env=dict(env))


def _parse_runtime_context_from_env() -> tuple[str | None, str | None, list[str] | None]:
    """读取 multi_node 运行时上下文环境变量。

    Returns:
        ``(rank_ip, master_ip, node_ips)``。若 ``NODE_IPS`` 缺失则 ``node_ips=None``。
    """
    rank_ip = os.environ.get("RANK_IP")
    master_ip = os.environ.get("MASTER_IP")
    # NODE_IPS 统一走 env_utils.parse_node_ips(先剥方括号再切分),避免 MaaS
    # 下发 "[ip1,ip2]" 时首尾 IP 粘上方括号导致 multi_node 选节点失配。
    node_ips = parse_node_ips(os.environ.get("NODE_IPS"))
    return rank_ip, master_ip, node_ips


def _render_env_dry_run(env_traces: dict[str, Any]) -> str:
    """使用正式脚本规则构建 dry-run 环境变量预览。"""
    lines = [
        render_env_export(env_key, traced.final_value, allow_unsafe=traced.allow_unsafe)
        for env_key, traced in env_traces.items()
        if traced.final_value is not None
    ]
    if not lines:
        return ""
    return "\n".join(["# Environment Variables", *lines])


def _print_env_dry_run(env_traces: dict[str, Any]) -> None:
    """打印 dry-run 环境变量预览，供直接调用方保持原有接口。"""
    preview = _render_env_dry_run(env_traces)
    if preview:
        print(preview)


def _render_system_setup_source_dry_run(engine: str, system_setup: Any) -> str:
    """构建当前节点或 Pod 会在 engine 前执行的 source 初始化命令预览。"""
    source_commands = build_system_setup_source_commands(engine, system_setup)
    if source_commands:
        return "\n".join(["# System Setup source commands", *render_source_command_blocks(source_commands)])
    return ""


def _print_system_setup_source_dry_run(engine: str, system_setup: Any) -> None:
    """打印当前节点或 Pod 会在 engine 前执行的 source 初始化命令。"""
    preview = _render_system_setup_source_dry_run(engine, system_setup)
    if preview:
        print(preview)


def _render_multi_node_dry_run(engine: str, nodes: List[Any]) -> str:
    """构建 dry-run 下的 multi_node 占位 argv 列表。

    Args:
        engine: 引擎名称。
        nodes: multi_node 占位节点列表。

    Returns:
        所有节点都成功渲染后的完整预览；任一节点失败时不返回部分内容。
    """
    sections: list[str] = []
    for node in nodes:
        node_argv = build_argv(node.engine_config_traces, engine=engine)
        section = [f"# node[{node.role}] (multi_node placeholder; runtime variables are not injected)"]
        env_preview = _render_env_dry_run(node.env_traces)
        if env_preview:
            section.append(env_preview)
        setup_preview = _render_system_setup_source_dry_run(engine, node.system_setup)
        if setup_preview:
            section.append(setup_preview)
        section.append(shlex.join(node_argv))
        sections.append("\n".join(section))
    return "\n".join(sections)


def _print_multi_node_dry_run(engine: str, nodes: List[Any]) -> None:
    """打印 dry-run 下的 multi_node 占位 argv 列表。"""
    preview = _render_multi_node_dry_run(engine, nodes)
    if preview:
        print(preview)


def _render_process_plan_dry_run(engine: str, resolved: Any) -> str:
    """构建 PD 当前 Pod 的 source 初始化命令及各进程预览。"""
    sections: list[str] = []
    setup_preview = _render_system_setup_source_dry_run(engine, resolved.system_setup)
    if setup_preview:
        sections.append(setup_preview)
    for process in resolved.process_plan.processes:
        section = [
            f"# process[{process.process_index}] rank={process.dp_rank} "
            f"devices={','.join(str(item) for item in process.visible_devices)}"
        ]
        env_preview = _render_env_dry_run(process.env_traces)
        if env_preview:
            section.append(env_preview)
        section.append(shlex.join(process.argv))
        sections.append("\n".join(section))
    return "\n".join(sections)


def _print_process_plan_dry_run(engine: str, resolved: Any) -> None:
    """打印 PD 当前 Pod 的 source 初始化命令及各进程预览。"""
    preview = _render_process_plan_dry_run(engine, resolved)
    if preview:
        print(preview)


def _print_multi_node_summary(engine: str, nodes: List[Any]) -> None:
    """打印真跑模式下的 multi_node 占位摘要。

    Args:
        engine: 引擎名称。
        nodes: multi_node 占位节点列表。

    Returns:
        None。
    """
    logger.info(
        "multi_node: %s nodes (placeholder; runtime variables are not injected; "
        "rerun wings-ctl in each Pod with RANK_IP/NODE_IPS)",
        len(nodes),
    )
    for node in nodes:
        node_argv = build_argv(node.engine_config_traces, engine=engine)
        logger.info("  [%s] argv: %s", node.role, shlex.join(node_argv))


def _run_dry_mode(
    parser: argparse.ArgumentParser,
    request: PipelineRequest,
    config_file: CustomConfigFile | None = None,
) -> None:
    """执行 dry-run 分支:解析后打印 argv,不落盘。

    Args:
        parser: CLI parser(用于友好报错)。
        request: 流水线请求(dry-run 与正常路径共用同一请求对象)。
        config_file: 自定义传参方式(--config-file)的已加载产物;None=常规路径。

    Returns:
        None。

    Raises:
        SystemExit: 通过 ``parser.error`` 触发。
    """
    engine = request.target.engine
    try:
        if config_file is not None:
            resolved = resolve_pipeline_custom(request, config_file)
        else:
            resolved = resolve_pipeline(request)

        if resolved.nodes:
            _print_multi_node_dry_run(engine, resolved.nodes)
            return
        if resolved.process_plan:
            _print_process_plan_dry_run(engine, resolved)
            return

        env_preview = _render_env_dry_run(resolved.env_traces)
        # 普通 argv 与结构化配置引擎统一通过启动计划展示。MindIE 预览包含外部
        # config 路径和领域覆盖摘要，但不会在 dry-run 阶段执行任何文件副作用。
        launch_preview = format_launch_dry_run_preview(resolved)
        print("\n".join(preview for preview in (env_preview, launch_preview) if preview))

    except (ValueError, FileNotFoundError, NotImplementedError) as exc:
        parser.error(str(exc))
        return


def _validate_unknown_args(unknown_args: List[str]) -> None:
    """校验未知参数：告警放行。

    Args:
        unknown_args: argparse 未识别参数列表。

    Returns:
        None。
    """
    if not unknown_args:
        return

    logger.warning(
        "Received unrecognized arguments (ignored, startup continues): %s; ",
        " ".join(unknown_args),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wings-ctl",
        description="Trace-first config resolver for vLLM engine startup.",
    )
    parser.add_argument(
        "--hardware-info",
        type=Path,
        default=None,
        help="Path to hardware_info.json (optional; default: /shared-volume/hardware_info.json)",
    )
    parser.add_argument(
        "--config-root",
        type=Path,
        default=None,
        help="Config assets root (default: auto-detect)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help="Output directory for scripts and audit (default: /shared-volume if present, else cwd)",
    )
    parser.add_argument(
        "--distributed",
        action="store_true",
        default=None,
        help="Distributed mode switch from MaaS; topology is derived from this flag plus PD_ROLE/NODE_IPS/MASTER_IP",
    )
    parser.add_argument(
        "--engine",
        default=None,
        help="Engine name (fallback: ENGINE env, else vllm)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Engine host override",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            "External proxy port (sidecar proxy default: 18000). "
            "This does not set the engine port: the engine listens on backend port 17000 by default. "
            "Use --engine-port or ENGINE_PORT to configure the engine port."
        ),
    )
    parser.add_argument(
        "--engine-port",
        type=int,
        default=None,
        help=(
            "Engine backend listen port override (fallback: ENGINE_PORT env, else model YAML). "
            "For PD exact recipes this overrides the backend port base; per-process ports remain base+index. "
            "The resulting range is validated against DP RPC, KV and proxy ports."
        ),
    )
    parser.add_argument(
        "--model-path",
        default=None,
        help="Model path override (engine_config.model)",
    )
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--served-model-name", default=None, help="Engine API model name override")
    parser.add_argument("--max-num-seqs", type=int, default=None)
    parser.add_argument("--max-num-batched-tokens", type=int, default=None)
    parser.add_argument("--input-length", type=int, default=None)
    parser.add_argument("--output-length", type=int, default=None)
    parser.add_argument("--trust-remote-code", action="store_true", default=None)
    parser.add_argument("--enable-auto-think-choice", action="store_true", default=None)
    parser.add_argument("--enable-auto-tool-choice", action="store_true", default=None)
    parser.add_argument("--dtype", default=None)
    parser.add_argument("--kv-cache-dtype", default=None)
    parser.add_argument("--quantization", default=None)
    parser.add_argument("--quantization-param-path", default=None)
    parser.add_argument("--gpu-memory-utilization", type=float, default=None)
    parser.add_argument("--block-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--enable-chunked-prefill", action="store_true", default=None)
    parser.add_argument("--enable-prefix-caching", action="store_true", default=None)
    parser.add_argument("--enable-expert-parallel", action="store_true", default=None)
    # 子系统特性开关:
    #   --enable-rag-acc:由 proxy/RAG 子系统消费,不进引擎 argv。
    #   --enable-smartqos / --enable-otlp-traces / --enable-metrics:
    #     进入 feature_switches,由 feature_inject 注入 engine_config/env;
    #     开关本身不作为 user_cli 原值直通 argv。
    parser.add_argument("--enable-rag-acc", action="store_true", default=None)
    parser.add_argument("--enable-smartqos", action="store_true", default=None)
    parser.add_argument("--enable-otlp-traces", action="store_true", default=None)
    parser.add_argument("--enable-metrics", action="store_true", default=None)
    parser.add_argument(
        "--device-count",
        type=int,
        default=None,
        help="GPU count from MaaS (fallback: DEVICE_COUNT env). Drives DP coordination "
        "(DP=count//TP; static TP; traced).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print argv to stdout without writing files",
    )
    parser.add_argument(
        "--license-file",
        type=Path,
        default=None,
        help=(
            "License file or directory containing exactly one *.xml, "
            "honored only by License-enabled builds "
            "(default: /etc/aiperf/license)"
        ),
    )
    parser.add_argument(
        "--gpu-usage-mode",
        type=str,
        default="full",
        help="GPU usage mode; enpu injects --enforce-eager for vLLM-Ascend (default: full)",
    )
    parser.add_argument(
        "--config-file",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to a custom JSON configuration. Uses resolve_custom_config: params come from JSON `params` "
            "instead of recipe/YAML, and `env` is injected before engine startup. "
            "JSON shape: {\\\"params\\\": {...}, \\\"env\\\": {...}}; both fields are optional."
        ),
    )
    return parser


def main() -> None:
    """CLI 入口函数。"""
    # CLI 入口是配置解析流水线的第一个执行点（先于 wings_control.py 导入），
    # 必须在此初始化统一日志格式，否则 pipeline 沿途模块（如 feature_overlay）
    # 的日志将使用 Python 默认格式，不符合 WINGS-CONTROL 规范。
    # 放在 main() 而非模块顶层，避免 import cli 时产生文件日志创建等副作用。
    setup_root_logging()
    parser = _build_parser()
    args, unknown_args = parser.parse_known_args()
    _validate_unknown_args(unknown_args)

    # 子系统特性开关留痕(实际消费见下方 feature_switches / proxy 子系统)。
    _received_subsys_switches = _collect_subsystem_switches(args)
    if _received_subsys_switches:
        logger.info("Received subsystem feature switches: %s", _received_subsys_switches)

    # --trust-remote-code 未显式开启时给出告警,但不阻断启动。
    if not args.trust_remote_code:
        logger.warning(
            "--trust-remote-code was not provided. The engine will not trust remote code; "
            "pass --trust-remote-code if the model requires custom Hugging Face code."
        )

    try:
        engine = _resolve_engine(args.engine)
        # ENGINE 是 health 等子进程选择扩展 profile 的跨进程事实。在入口显式
        # 传播规范化结果，避免 CLI 与部署 env 识别不一致。
        os.environ["ENGINE"] = engine
        hardware_info_path = _resolve_hardware_info_path(args.hardware_info)
        device_count = _resolve_device_count(args.device_count)
        # License 构建(device_count 必填)的前移强校验:必须在任何依赖
        # device_count 的校验(尤其 resolve_config 的 TP-shrink 前置闸)之前,
        # 缺失/非正整数以唯一可检索的 code=2016 device_count_unknown 拒绝,
        # 避免 None 落入 TP-shrink 后误导性的 hardware_family 报错。
        # 普通构建(Null 门禁)直通,device_count 仍为可选。
        validate_device_count_early(device_count)
        # 显式副作用:把 --port(对外/代理端口)写入 env PORT,供 proxy 子系统读取(独立成步,不藏在参数收集里)。
        _export_proxy_port(args.port)

        # ENABLE_SMARTQOS 需要被 proxy 子进程消费（Anthropic 协议转换门控）。
        _export_smartqos_env(args.enable_smartqos)
        _export_rag_acc_env(args.enable_rag_acc)
        raw_user_cli_overrides = _collect_user_cli_overrides(
            host=args.host,
            port=args.port,
            model_path=args.model_path,
            engine_port=args.engine_port,
            model_name=args.model_name,
            served_model_name=args.served_model_name,
            max_num_seqs=args.max_num_seqs,
            max_num_batched_tokens=args.max_num_batched_tokens,
            input_length=args.input_length,
            output_length=args.output_length,
            trust_remote_code=args.trust_remote_code,
            enable_auto_think_choice=args.enable_auto_think_choice,
            enable_auto_tool_choice=args.enable_auto_tool_choice,
            dtype=args.dtype,
            kv_cache_dtype=args.kv_cache_dtype,
            quantization=args.quantization,
            quantization_param_path=args.quantization_param_path,
            gpu_memory_utilization=args.gpu_memory_utilization,
            block_size=args.block_size,
            seed=args.seed,
            enable_chunked_prefill=args.enable_chunked_prefill,
            enable_prefix_caching=args.enable_prefix_caching,
            enable_expert_parallel=args.enable_expert_parallel,
            enable_smartqos=args.enable_smartqos,
            enable_otlp_traces=args.enable_otlp_traces,
            enable_metrics=args.enable_metrics,
        )
        user_cli_overrides, user_cli_dropped = CLITranslator.translate_overrides(raw_user_cli_overrides, engine)
        user_cli_overrides = _apply_gpu_usage_mode(
            user_cli_overrides,
            args.gpu_usage_mode,
            engine,
        )
        # 特性开关本身不直接渲染进 argv,只提取为 ON 的开关传入 resolve_config:
        #   enable_auto_tool_choice / enable_auto_think_choice → feature_overlay 按 model.yaml features 渲染;
        #   enable_smartqos / enable_otlp_traces / enable_metrics → feature_inject 按引擎类型注入 engine_config/env。
        feature_switch_keys = (
            "enable_auto_tool_choice",
            "enable_auto_think_choice",
            "enable_smartqos",
            "enable_otlp_traces",
            "enable_metrics",
        )
        feature_switches = {
            k: raw_user_cli_overrides[k]
            for k in feature_switch_keys
            if raw_user_cli_overrides.get(k)
        }
        # MaaS CLI is the authoritative RAG switch: omitted means explicitly disabled.
        feature_switches["enable_rag_acc"] = bool(args.enable_rag_acc)
    except ValueError as exc:
        parser.error(str(exc))
        return

    # 先规范化运行时上下文和 PD 原子输入，再由大策略层推导 topology；两步都不读 YAML。
    rank_ip, master_ip, node_ips = _parse_runtime_context_from_env()
    # Mooncake master 专属 Pod 身份(部署层事实,与推理集群上下文无关):pre_template
    # 据此豁免标准多机的 MASTER_IP 强校验,交付层(script_builder)据此走 master 支线。
    mooncake_master_pod = is_mooncake_master_pod()
    placement = None
    if rank_ip or node_ips or master_ip:
        placement = ClusterPlacement(rank_ip=rank_ip, node_ips=node_ips, master_ip=master_ip)
    try:
        pd_input, pd_role_missing_legacy = parse_pd_runtime_input(
            os.environ.get("PD_ROLE"),
            os.environ,
            placement,
            distributed=bool(args.distributed),
        )
        engine, topology = pre_template_strategy(
            engine,
            distributed=args.distributed,
            pd_role=pd_input.role if pd_input else None,
            master_ip=master_ip,
            is_mooncake_master=mooncake_master_pod,
        )
    except ValueError as exc:
        parser.error(str(exc))
        return

    if pd_input is not None:
        user_cli_overrides, user_cli_dropped = _drop_pd_backend_port_compat(
            user_cli_overrides,
            user_cli_dropped,
        )

    # 配方标识:--model-name(模型名称)或从 --model-path basename 推导。
    try:
        model_name = _resolve_model_name(args.model_name, args.model_path)
    except ValueError as exc:
        parser.error(str(exc))
        return

    request = PipelineRequest(
        target=Target(model_name=model_name, topology=topology, engine=engine),
        hardware_info_path=hardware_info_path,
        config_root=args.config_root,
        user_input=UserInput(
            cli_overrides=user_cli_overrides,
            cli_dropped=user_cli_dropped,
            feature_switches=feature_switches,
            engine_port=args.engine_port,
        ),
        device_count=device_count,
        placement=placement,
        pd_input=pd_input,
        pd_role_missing_legacy=pd_role_missing_legacy,
        license_file=args.license_file,
    )

# 自定义传参方式(--config-file)分派:有 → 走独立 custom 支线(跳过 recipe);
    # 无 → 走现有 resolve_pipeline(完全不变,§2.3 支线 A)。
    # 贯彻"用户自管":params 与 env 均未传时**仍走 custom 支线**,不等价于 --config-file 未传
    # (用户显式传入 --config-file 即表达"走自定义、参数以我为准、由我负责"的意图)。
    config_file: CustomConfigFile | None = None
    if args.config_file is not None:
        try:
            config_file = _load_config_file(args.config_file)
        except ValueError as exc:
            parser.error(str(exc))
            return

    if args.dry_run:
        _run_dry_mode(parser, request, config_file=config_file)
        return

    try:
        if config_file is not None:
            resolved, start_path, repro_path, audit_path = run_pipeline_custom(
                request, config_file, output_dir=_resolve_output_dir(args.output_dir)
            )
        else:
            resolved, start_path, repro_path, audit_path = run_pipeline(
                request, output_dir=_resolve_output_dir(args.output_dir)
            )
    except (ValueError, FileNotFoundError, NotImplementedError) as exc:
        # 配置缺失(硬件/engine 无资产)/ 未支持的 topology / 强校验失败 → 友好报错,不抛 traceback
        parser.error(str(exc))
        return

    if resolved.nodes:
        # multi_node 占位(无运行时上下文):顶层无扁平 argv,逐节点打印。
        _print_multi_node_summary(engine, resolved.nodes)
    elif resolved.process_plan:
        for process in resolved.process_plan.processes:
            logger.info(
                "process[%d] rank=%s argv: %s",
                process.process_index,
                process.dp_rank,
                shlex.join(process.argv),
            )
    else:
        logger.info("%s", format_launch_summary(resolved))
    logger.info("start_command: %s", start_path)
    logger.info("repro:         %s", repro_path)
    logger.info("audit:         %s", audit_path)


if __name__ == "__main__":
    main()
