"""ScriptBuilder — 从 ResolvedConfig 产出 start_command.sh 和 repro.sh。

输入: ResolvedConfig, output_dir (Path)
输出: 写入 start_command.sh + repro.sh 到 output_dir

区别:
- start_command.sh: 本次实际执行脚本,简洁。
- repro.sh: 可移植复现脚本,包含完整 env 设置 + 每个引擎参数的来源注释(取自 trace)。

⚠️ env 渲染与 system_setup 渲染为安全敏感代码,需人工 review。
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from wings_ctl.core.models import ResolvedConfig, SystemSetup, TracedValue
from wings_ctl.core.topology import Topology
from wings_ctl.engines.vllm_adapter import (
    MODEL_KEYS,
    build_argv,
    build_command_head,
    render_param_tokens,
    resolve_model_traced,
)
from wings_ctl.rendering.env_renderer import render_env_export


def _render_env_section(env_traces: Dict[str, TracedValue]) -> List[str]:
    """渲染 env export 段。"""
    lines: List[str] = []
    for env_key, traced in env_traces.items():
        if traced.final_value is not None:
            lines.append(render_env_export(env_key, traced.final_value))
    return lines


def _render_system_setup_comments(
    system_setup: Optional[SystemSetup],
    *,
    include_commands: bool = True,
) -> List[str]:
    """渲染 system_setup 为注释形式(不生成可执行行)。

    ⚠️ 安全敏感:仅输出注释,不生成可执行指令。特权 sysctls / sysfs_writes **恒注释**
    (维持单机「注释不执行」安全立场,留运维/容器 init)。

    Args:
        system_setup: 系统级设置(None 返回空)。
        include_commands: 是否把 commands 也以注释列出。multi_node 执行路径下 commands 已
            inline 渲染(见 ``_render_runtime_commands_inline``),此处传 False 避免重复。
    """
    if system_setup is None:
        return []
    lines: List[str] = []

    has_any = system_setup.sysctls or system_setup.sysfs_writes or (
        include_commands and system_setup.commands
    )
    if has_any:
        lines.append(
            f"# ─── System Setup (source: {system_setup.source_file} "
            f"@ {system_setup.source_path}) ───"
        )

    if system_setup.sysctls:
        lines.append("# sysctls:")
        for key, value in system_setup.sysctls.items():
            lines.append(f"#   sysctl -w {key}={value}")

    if system_setup.sysfs_writes:
        lines.append("# sysfs_writes:")
        for entry in system_setup.sysfs_writes:
            path = entry.get("path", "")
            value = entry.get("value", "")
            lines.append(f"#   echo {value!r} > {path}")

    if include_commands and system_setup.commands:
        lines.append(f"# commands ({len(system_setup.commands)} entries, not rendered)")

    if lines:
        lines.append("")

    return lines


def _render_runtime_commands_inline(system_setup: Optional[SystemSetup]) -> List[str]:
    """把 system_setup.commands 渲染为**可执行** inline 行(multi_node)。

    multi_node 路径下,这里当前只会执行框架内固定命令(NIC 探测)。
    占位 ``$local_ip`` / ``$node0_ip`` 在上游已替换为字面值,不在这里赋值。
    ⚠️ 若将来扩展新的 inline 命令,需要同步做人审安全评估。
    特权 sysctls / sysfs_writes 不在此,仍走注释(``_render_system_setup_comments``)。

    Args:
        system_setup: 系统级设置(None / 无 commands 返回空)。

    Returns:
        inline 可执行命令行(含来源注释头);置于 env export 之前,使 ``$var`` 先定义。
    """
    if system_setup is None or not system_setup.commands:
        return []
    lines = [
        f"# ─── runtime commands (inline; source: {system_setup.source_file} "
        f"@ {system_setup.source_path}) ───",
    ]
    lines.extend(system_setup.commands)
    lines.append("")
    return lines


def _render_accel_install_preamble(engine: str, engine_version: str, packages: List[str]) -> List[str]:
    """渲染 wings-accel runtime patch 安装段(``--config`` JSON 形式)。

    2026-07-06 更新:从 3 个位置参数改为 ``--config '{json}'``;JSON 含
    ``engine{name,version}`` + ``packages``(各选中 scheme 声明的 pip 依赖,name:version 字符串)。
    ``hardware_family`` 不再传入(新契约;若 install.py 仍需,加 ``"hardware"`` 字段即可)。

    ⚠️ 安全敏感:本行 exec,**改命令形态须 A5 人工 review**(对齐 §2.8 / docs/45 §5.3)。
    JSON 用 ``json.dumps`` 生成(无单引号)再 ``shlex.quote`` 整体包住,杜绝注入。

    Args:
        engine: 引擎名(如 ``vllm``)。
        engine_version: 引擎版本(可带或不带 ``v`` 前缀;此处统一补 ``v`` 前缀)。
        packages: 选中 scheme 声明的依赖包列表(``name:version`` 字符串);空 → ``"packages": []``。

    Returns:
        单行 install 命令(JSON 已 ``shlex.quote``)+ 收尾空行。
    """
    version = engine_version if not engine_version or engine_version.startswith("v") else f"v{engine_version}"
    config = {
        "engine": {"name": engine, "version": version},
        "packages": list(packages),
    }
    config_json = json.dumps(config)
    return [
        f"python3 /accel-volume/install.py --config {shlex.quote(config_json)}",
        "",
    ]




def _render_accel_env_section(accel_env: Dict[str, str]) -> List[str]:
    """渲染 wings-accel 注入的 env export 段。

    Args:
        accel_env: ``AccelResult.env``(智能加速产出的环境变量;空 → 返回空)。

    Returns:
        ``export K=V`` 行列表(空 dict → 空列表,调用方据此决定是否插入空行/注释)。
    """
    lines: List[str] = []
    for env_key, value in accel_env.items():
        if value is not None:
            lines.append(render_env_export(env_key, value))
    return lines


def _render_start_command_sh(
    argv: List[str],
    env_traces: Dict[str, TracedValue],
    system_setup: Optional[SystemSetup],
    *,
    engine: str,
    engine_version: str,
    packages: List[str],
    execute_commands: bool = False,
    accel_env: Optional[Dict[str, str]] = None,
    accel_enabled: bool = False,
) -> str:
    """生成 start_command.sh 内容。简洁执行脚本。

    Args:
        argv: 引擎命令 argv(含 accel 参数——accel.engine_config 已并入 engine_config_traces)。
        env_traces: env 逐项 trace。
        system_setup: 系统级设置。
        engine: 引擎名称,传给 wings-accel install.py。
        engine_version: 引擎版本,传给 wings-accel install.py。
        packages: 选中 scheme 声明的 pip 依赖(name:version),传给 install.py ``--config``。
        execute_commands: multi_node 已完成运行时注入时为 True;runtime commands 需要
            在 env export 之前执行,使 ``$local_ip`` 等变量先定义。standalone 为 False,
            系统设置命令只作为注释渲染。
        accel_env: wings-accel 注入的环境变量,并入 env export 段;None/空 → 不变。
        accel_enabled: wings-accel 是否真启用(``AccelResult.enabled``)。仅 True 时渲染
            runtime patch 安装段;False(未开/模块缺席)→ 不加,非 accel 路径零影响。
    """
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
    ]

    # multi_node:runtime commands inline(必须在 env 之前,$var 先定义)
    if execute_commands:
        cmd_lines = _render_runtime_commands_inline(system_setup)
        if cmd_lines:
            lines.extend(cmd_lines)

    # env exports(trace 段 + wings-accel 注入段)
    env_lines = _render_env_section(env_traces)
    env_lines.extend(_render_accel_env_section(accel_env or {}))
    if env_lines:
        lines.extend(env_lines)
        lines.append("")

    # system_setup 注释(特权 sysctls/sysfs 恒注释;commands 若已 inline 则不重复)
    setup_lines = _render_system_setup_comments(system_setup, include_commands=not execute_commands)
    if setup_lines:
        lines.extend(setup_lines)

    # wings-accel runtime patch 安装段(仅 accel 真启用时)
    if accel_enabled:
        lines.extend(_render_accel_install_preamble(engine, engine_version, packages))

    # exec engine command
    lines.append("exec " + shlex.join(argv))
    lines.append("")
    return "\n".join(lines)


def _render_repro_sh(
    resolved: ResolvedConfig,
    *,
    execute_commands: bool = False,
) -> str:
    """生成 repro.sh 内容。可移植复现脚本,含来源注释。

    直接遍历 resolved.engine_config_traces 生成带注释的参数行,
    不从 argv 字符串反推 key/结构(避免脆弱的反向映射)。
    渲染规则复用 vllm_adapter.render_param_tokens(同一套逻辑,不重复实现)。

    Args:
        resolved: 解析结果。
        execute_commands: multi_node 已注入时为 True → runtime commands inline(env 之前)。
    """
    lines = [
        "#!/usr/bin/env bash",
        "# ─── Reproducibility Script ───",
        f"# Generated from: {', '.join(resolved.source_files)}",
        f"# Hardware: {resolved.hardware.hardware_family}",
        f"# Engine: {resolved.engine} v{resolved.engine_version.resolved}",
        f"# Topology: {resolved.topology.value}",
        "",
        "set -euo pipefail",
        "",
    ]

    # multi_node:runtime commands inline(env 之前)
    if execute_commands:
        cmd_lines = _render_runtime_commands_inline(resolved.system_setup)
        if cmd_lines:
            lines.extend(cmd_lines)

    # env section with trace comments
    if resolved.env_traces:
        lines.append("# ─── Environment Variables ───")
        for env_key, traced in resolved.env_traces.items():
            if traced.final_value is not None:
                lines.append(f"# source: {traced.source_file} @ {traced.source_path}")
                lines.append(render_env_export(env_key, traced.final_value))
        lines.append("")

    # wings-accel 注入的 env(与 trace 解耦,单独标注来源)
    accel_env_lines = _render_accel_env_section(resolved.accel.env)
    if accel_env_lines:
        lines.append("# ─── Environment Variables (wings-accel) ───")
        lines.extend(accel_env_lines)
        lines.append("")

    # system_setup (注释形式,含来源;commands 若已 inline 则不重复)
    setup_lines = _render_system_setup_comments(
        resolved.system_setup, include_commands=not execute_commands
    )
    if setup_lines:
        lines.extend(setup_lines)

    # command section — 来源注释块 + 单行 exec(避免续行与注释交互风险)
    lines.append("# ─── Engine Command 参数来源 ───")

    # 命令头(前缀 + model):按命令规格查表分派 model 形态(vllm 位置 / sglang --model-path)
    # model 取 canonical "model" 或别名 "model_path"(sglang recipe),与 build_argv 一致。
    model_traced = resolve_model_traced(resolved.engine_config_traces)
    model_value = str(model_traced.final_value) if model_traced else ""
    command_tokens: List[str] = build_command_head(resolved.engine, model_value)

    # 来源注释: model(命令头整段作注释)
    if model_traced:
        model_file = Path(model_traced.source_file).name
        model_cmd = shlex.join(command_tokens)
        lines.append(
            f"#   {model_cmd}   <- {model_traced.final_layer} ({model_file})"
        )

    # 收集参数(命令 token + 来源注释)
    for key, traced in resolved.engine_config_traces.items():
        if key in MODEL_KEYS:  # model / model_path 已由命令头渲染,跳过避免重复
            continue
        tokens = render_param_tokens(key, traced.final_value)
        if tokens is None:
            continue
        command_tokens.extend(tokens)

        if len(tokens) == 1:
            rendered_for_comment = tokens[0]
        else:
            rendered_for_comment = f"{tokens[0]} {shlex.quote(tokens[1])}"
        source_file_name = Path(traced.source_file).name
        lines.append(
            f"#   {rendered_for_comment}   <- {traced.final_layer} ({source_file_name})"
        )

    # 注:accel.engine_config 已作为 strategy_accel 合并层进 engine_config_traces,
    # 上方主循环已渲染并标来源,这里无需重复追加。

    lines.append("exec " + shlex.join(command_tokens))

    lines.append("")
    return "\n".join(lines)


_MULTI_NODE_BANNER = [
    "# ============================================================================",
    "# MULTI-NODE — RUNTIME INJECTION PENDING (无运行时上下文 RANK_IP/NODE_IPS)",
    "# 本脚本为【占位】:nodes[] 已加载并完成深合并,但未选定本 Pod / 未注入。",
    "# 部署时由 wings-ctl 在各 Pod 携 RANK_IP/NODE_IPS/MASTER_IP 重跑,产可执行脚本。",
    "# 下方每个节点的 argv/env 中 $占位符 为【字面未解析】值,仅供 review。",
    "# ⚠️ 切勿直接执行本脚本。",
    "# ============================================================================",
]


def _render_multi_node_placeholder(resolved: ResolvedConfig) -> str:
    """渲染 multi_node 占位脚本(无运行时上下文):不产 ``exec``,不假装可跑。

    顶部横幅声明"未注入";每节点一段**注释化**的 env + argv(``$占位符`` 字面);
    脚本主体只 echo + 非零退出,显式阻断误执行。

    Args:
        resolved: 解析结果(``resolved.nodes`` 必须非空)。

    Returns:
        占位 start_command.sh / repro.sh 文本。
    """
    lines = ["#!/usr/bin/env bash"]
    lines.extend(_MULTI_NODE_BANNER)
    lines.append("set -euo pipefail")
    lines.append('echo "multi_node 占位脚本:未注入(缺 RANK_IP/NODE_IPS),请勿直接执行" >&2')
    lines.append("exit 3")
    lines.append("")

    for i, node in enumerate(resolved.nodes or []):
        idx = f" index={node.index}" if node.index is not None else ""
        lines.append(f"# ─── node[{i}] role={node.role}{idx} (source: {node.source_prefix}) ───")
        env_lines = _render_env_section(node.env_traces)
        if env_lines:
            lines.append("#   env (未注入):")
            for env_line in env_lines:
                lines.append(f"#     {env_line}")
        setup_lines = _render_system_setup_comments(node.system_setup)
        for setup_line in setup_lines:
            if setup_line:
                lines.append(f"# {setup_line}")
            else:
                lines.append("#")
        argv = build_argv(node.engine_config_traces, engine=resolved.engine)
        lines.append("#   argv (未注入,$占位符为字面值):")
        lines.append(f"#     {shlex.join(argv)}")
        lines.append("")
    return "\n".join(lines)


def build_scripts(
    resolved: ResolvedConfig,
    output_dir: Path,
) -> Tuple[Path, Path]:
    """生成 start_command.sh 和 repro.sh 并写入 output_dir。

    三条路径:
    - multi_node 占位(``resolved.nodes`` 非空,无运行时上下文)→ 占位脚本(无 exec,exit 3)。
    - multi_node 已注入(topology==MULTI_NODE 且已选 node)→ 可执行,commands inline。
    - standalone → 可执行,commands 维持注释。

    Returns:
        (start_command_path, repro_path) 元组。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    start_path = output_dir / "start_command.sh"
    repro_path = output_dir / "repro.sh"

    if resolved.nodes:
        # multi_node 占位:两件产物同为占位脚本,显式阻断误执行。
        # 占位脚本不 exec,也不追加 accel 产出。
        placeholder = _render_multi_node_placeholder(resolved)
        start_path.write_text(placeholder, encoding="utf-8")
        start_path.chmod(0o755)
        repro_path.write_text(placeholder, encoding="utf-8")
        repro_path.chmod(0o755)
        return start_path, repro_path

    # multi_node 已注入 → commands inline 执行;standalone → 注释(现状)。
    execute_commands = resolved.topology == Topology.MULTI_NODE

    # accel.engine_config 已作为 strategy_accel 合并层并入 engine_config_traces,
    # build_argv 自动渲染(深合并 + 去重 + 带 trace),无需在此 append。
    argv = build_argv(resolved.engine_config_traces, engine=resolved.engine)
    start_content = _render_start_command_sh(
        argv,
        resolved.env_traces,
        resolved.system_setup,
        engine=resolved.engine,
        # install preamble 使用实际引擎版本(优先 requested,回退 resolved)。
        engine_version=resolved.engine_version.requested or resolved.engine_version.resolved,
        packages=resolved.accel.packages,
        execute_commands=execute_commands,
        accel_env=resolved.accel.env,
        accel_enabled=resolved.accel.enabled,
    )
    start_path.write_text(start_content, encoding="utf-8")
    start_path.chmod(0o755)

    repro_content = _render_repro_sh(resolved, execute_commands=execute_commands)
    repro_path.write_text(repro_content, encoding="utf-8")
    repro_path.chmod(0o755)

    return start_path, repro_path
