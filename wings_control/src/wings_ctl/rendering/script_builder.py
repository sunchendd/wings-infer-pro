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
import logging
import os
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from wings_ctl.common.settings import settings
from wings_ctl.core.models import ResolvedConfig, SystemSetup, TracedValue
from wings_ctl.core.topology import Topology
from wings_ctl.engines.registry import build_launch_plan
from wings_ctl.engines.vllm_adapter import (
    MODEL_KEYS,
    build_argv,
    build_command_head,
    render_param_tokens,
    resolve_model_traced,
)
from wings_ctl.rendering.env_renderer import render_env_export

logger = logging.getLogger(__name__)


def _render_env_section(env_traces: Dict[str, TracedValue]) -> List[str]:
    """渲染 env export 段。

    逐项读 ``TracedValue.allow_unsafe``:config_file env 层(allow_unsafe=True)跳过
    _validate_dollar_value 安全校验,双引号放行 ``$(hostname)`` 等命令替换
    (用户对自己的输入负责,见 resolve_custom_config)。
    """
    lines: List[str] = []
    for env_key, traced in env_traces.items():
        if traced.final_value is not None:
            lines.append(
                render_env_export(env_key, traced.final_value, allow_unsafe=traced.allow_unsafe)
            )
    return lines


def _render_system_setup_comments(system_setup: Optional[SystemSetup]) -> List[str]:
    """渲染 system_setup 为注释形式(不生成可执行行)。

    ⚠️ 安全敏感:仅输出注释,不生成可执行指令。特权 sysctls / sysfs_writes **恒注释**
    (维持单机「注释不执行」安全立场,留运维/容器 init)。

    Args:
        system_setup: 系统级设置(None 返回空)。
    """
    if system_setup is None:
        return []
    lines: List[str] = []

    has_any = system_setup.sysctls or system_setup.sysfs_writes or system_setup.commands
    if has_any:
        lines.append(f"# ─── System Setup (source: {system_setup.source_file} @ {system_setup.source_path}) ───")

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

    if system_setup.commands:
        lines.append(f"# commands ({len(system_setup.commands)} entries, not rendered)")

    if lines:
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


def _write_advanced_features_json(resolved: ResolvedConfig) -> None:
    """写 advanced_features.json(加速特性使能状态,页面回显的单一真相源)。

    对齐老仓库 wings_entry._write_advanced_features_json:在脚本生成阶段写入共享卷,
    health 接口 ``/v1/startup/accel``(读 ``settings.ADVANCED_FEATURES_FILE``)透出给页面。
    字段语义(接口文档):
      - features:4 个特性最终使能布尔(页面开关唯一回显依据);
      - variants:实际策略字符串(features[x]=false 时为 null,仅诊断用);
      - others.kv_mem_offload_size:智能推荐容量(auto 估算的最终推荐值,GB;0=低于下限,
        null=无有效容量),来自 ``accel.kv_mem_offload_size_gb``;
      - others.speculative_decode:投机推理详情(method/num_speculative_tokens 等),未产出 → null。
    写失败只 WARN 不抛(状态文件缺失时 health 接口按空对象兜底)。

    Args:
        resolved: 配置解析最终产物(``resolved.accel`` 承载 wings-accel 产出)。
    """
    accel = resolved.accel
    # features:有选中 scheme 即该特性最终生效(scheme 名即 variants 策略);
    # sparse_kv 只按 MaaS 开关开且 smart 命中 sparse scheme 回显(recipe 基线 fp8 不算)
    decoding_scheme = accel.audit.get("smart_decoding_scheme") if accel.audit else None
    sparse_scheme = accel.audit.get("smart_kv_sparse_scheme") if accel.audit else None
    offload_scheme = accel.audit.get("smart_kv_cache_scheme") if accel.audit else None
    rag_acc_trace = resolved.env_traces.get("RAG_ACC_ENABLED")
    rag_acc_value = rag_acc_trace.final_value if rag_acc_trace is not None else os.getenv("RAG_ACC_ENABLED")
    rag_acc_enabled = str(rag_acc_value or "").strip().lower() in {"1", "true", "yes", "on"}

    features = {
        "speculative_decode": bool(decoding_scheme),
        "sparse_kv": bool(sparse_scheme),
        "kv_offload": bool(offload_scheme),
        "rag_acc": rag_acc_enabled,
    }
    variants = {
        "speculative_decode": decoding_scheme or None,
        "sparse_kv": sparse_scheme or None,
        "kv_offload": offload_scheme or None,
    }
    spec_details = None
    if decoding_scheme:
        spec_config = (
            resolved.engine_config_traces.get("speculative_config").final_value
            if "speculative_config" in resolved.engine_config_traces
            else None
        )
        if isinstance(spec_config, dict):
            spec_details = dict(spec_config)

    data = {
        "engine": resolved.engine,
        "features": features,
        "variants": variants,
        "others": {
            "kv_mem_offload_size": accel.kv_mem_offload_size_gb,
            "speculative_decode": spec_details,
        },
    }
    path = Path(settings.ADVANCED_FEATURES_FILE)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        logger.info(
            "Wrote advanced_features.json: features=%s variants=%s others=%s",
            features, variants, data["others"],
        )
    except OSError as exc:
        logger.warning("Failed to write advanced_features.json: %s", exc)


def _render_kv_disk_cleanup_section(kv_disk_offload_path: Optional[str]) -> List[str]:
    """渲染 KV 磁盘卸载残留清理段(vllm serve 前)。

    背景:LMCache disk 卸载的数据落盘在 ``KV_DISK_OFFLOAD_PATH`` 下,推理服务
    重启后旧数据残留,与新一轮卸载数据叠加会超出 MaaS 规划的 KV_DISK_OFFLOAD_SIZE,
    同主机上可能与其它服务争抢资源。启动前清空卸载目录,保证本次服务占用与规划一致。

    清理目标为 ``KV_DISK_OFFLOAD_PATH`` 目录下的 ``*.pt`` 文件(卸载数据落盘形态,
    不追加子目录后缀);path 为 None(无磁盘卸载)→ 空列表(非 disk 路径零影响)。

    ⚠️ rm 属安全敏感命令:路径来自 MaaS ``KV_DISK_OFFLOAD_PATH``(accel 产出已解析,
    非用户 shell 输入),且 ``shlex.quote`` 整体转义,杜绝通配/注入;改动命令形态须人工 review。
    """
    if not kv_disk_offload_path:
        return []
    target = kv_disk_offload_path.rstrip("/")
    return [
        "# ── KV 磁盘卸载残留清理:服务重启后旧 KV 落数据会超出规划容量,启动前清空 ──",
        f"mkdir -p {shlex.quote(target)}",
        f"rm -f {shlex.quote(target)}/*.pt",
        "",
    ]


def _render_accel_pre_serve_section(
    pre_serve: Optional[List[str]],
    pre_serve_master: Optional[List[str]],
    pre_serve_client: Optional[List[str]] = None,
) -> List[str]:
    """渲染 KV 存储后端(memcache/mooncake)pre-serve 段。

    三段(对齐 start_kv_serve.sh:install.py → 起 KV 服务 → vllm serve):
    - ``pre_serve``:所有节点运行(典型:heredoc 生成 mooncake.json/mmc_*.conf,引用 $local_ip/$node0_ip);
    - ``pre_serve_master``:仅 master 节点起 daemon。包运行时条件
      ``RANK_IP == MASTER_IP`` 判 master;单机(``MASTER_IP`` 未设)条件恒真 → 起 daemon。
    - ``pre_serve_client``:仅 client 节点(非 master)。包运行时条件 ``RANK_IP != MASTER_IP``
      判 client;单机(``MASTER_IP`` 未设)条件恒假 → 不跑(单机即 master)。

    Args:
        pre_serve: 所有节点命令;空 → 不渲染该段。
        pre_serve_master: 仅 master 命令;空 → 不渲染该段(external 模式或无 daemon)。
        pre_serve_client: 仅 client 命令;空 → 不渲染该段。

    Returns:
        pre-serve 段脚本行;三段皆空 → 空列表(非 KV 后端路径零影响)。
    """
    lines: List[str] = []
    if pre_serve:
        lines.append("# ─── KV store pre-serve (all nodes) ───")
        lines.extend(pre_serve)
        lines.append("")
    if pre_serve_master:
        lines.append("# ─── KV store pre-serve (master only) ───")
        lines.append('if [ -z "${MASTER_IP:-}" ] || [ "${RANK_IP:-}" = "${MASTER_IP:-}" ]; then')
        lines.extend(f"    {cmd}" for cmd in pre_serve_master)
        lines.append("fi")
        lines.append("")
    if pre_serve_client:
        lines.append("# ─── KV store pre-serve (client only) ───")
        lines.append('if [ -n "${MASTER_IP:-}" ] && [ "${RANK_IP:-}" != "${MASTER_IP:-}" ]; then')
        lines.extend(f"    {cmd}" for cmd in pre_serve_client)
        lines.append("fi")
        lines.append("")
    return lines


def _build_analyzer_config(resolved: ResolvedConfig) -> dict:
    """从 ResolvedConfig 投影为 log_analyzer 实际消费的 analyzer_config dict。

    log_analyzer 在引擎容器中作为后台进程运行,通过 ``--config`` 接收 JSON 配置。
    经代码审计,log_analyzer 仅消费以下 4 个字段:
    - ``engine``: 插件选择(PatternPluginManager.PLUGIN_MAPPING 的 key)
    - ``deployment_mode``: 插件选择(同上)
    - ``hardware``: 插件选择(同上)
    - ``backend_port``: 健康探测(_probe_backend_health 的 URL 端口)

    Args:
        resolved: 配置解析最终产物。

    Returns:
        analyzer_config dict,仅含 log_analyzer 实际消费的 4 个字段。
    """
    is_multi_node = resolved.topology == Topology.MULTI_NODE

    # backend_port: 从 engine_config_traces 提取,回退默认 17000
    backend_port = 17000
    port_traced = resolved.engine_config_traces.get("port")
    if port_traced and port_traced.final_value is not None:
        try:
            backend_port = int(port_traced.final_value)
        except (TypeError, ValueError):
            pass

    return {
        "engine": resolved.engine,
        "deployment_mode": "distributed" if is_multi_node else "single",
        "hardware": resolved.hardware.device,
        "backend_port": backend_port,
    }


def _build_analyzer_preamble(resolved: ResolvedConfig) -> Optional[str]:
    """生成 log_analyzer shell 片段(仅 standalone 或 multi_node master 节点)。

    log_analyzer 作为 ``start_command.sh`` 中的后台进程,在引擎启动前启动,
    通过 ``tail -F`` 跟踪引擎日志,匹配阶段模式,写入 ``progress.jsonl``。

    跳过条件:
    - multi_node 占位脚本(``resolved.nodes`` 非空)→ 不注入
    - multi_node worker 节点(node_rank > 0)→ 不注入

    运行时模块路径: log_analyzer 在构建时被单独拷贝到 ``/opt/log_analyzer``(避免 pyc 编译),
    再由 ``wings_start.sh`` 拷贝到 ``/shared-volume/log_analyzer``,因此启动命令使用
    ``cd /shared-volume && python3 -B -m log_analyzer.log_analyzer``(顶层包名,非 wings_ctl 子包)。

    Args:
        resolved: 配置解析最终产物。

    Returns:
        log_analyzer shell 片段字符串;跳过时返回 None。
    """
    # multi_node 占位脚本不注入(无运行时上下文,不可执行)
    if resolved.nodes:
        return None

    is_multi_node = resolved.topology == Topology.MULTI_NODE
    node_rank = int(resolved.resolution_notes.get("multi_node_index", 0)) if is_multi_node else 0

    # worker 节点跳过(仅 master 运行分析器)
    if is_multi_node and node_rank > 0:
        return None

    analyzer_config = _build_analyzer_config(resolved)
    config_json = json.dumps(analyzer_config)
    # shell 单引号安全转义: ' → '"'"'
    config_escaped = config_json.replace("'", "'\"'\"'")
    # progress.jsonl 必须写入共享卷,与 proxy 的 settings.PROGRESS_FILE 路径一致
    # (proxy 通过 settings.PROGRESS_FILE 读取进度)
    progress_file = settings.PROGRESS_FILE

    # 从模板文件加载 shell 片段,注入动态变量。
    # 模板文件有 shell 语法高亮,可独立 bash -n 验证,Python 代码更简洁。
    template_path = Path(__file__).parent / "templates" / "analyzer_preamble.sh.tmpl"
    template = template_path.read_text(encoding="utf-8")
    return (
        template.replace("{ANALYZER_CONFIG}", config_escaped)
        .replace("{PROGRESS_FILE}", progress_file)
        .replace("{ENGINE_LOG}", settings.ENGINE_LOG_FILE)
        .replace("{ENGINE_FULL_LOG}", settings.ENGINE_FULL_LOG_FILE)
        .replace("{SHARED_VOLUME}", settings.SHARED_VOLUME_PATH)
    )


def _render_start_command_sh(
    argv: List[str],
    env_traces: Dict[str, TracedValue],
    system_setup: Optional[SystemSetup],
    *,
    engine: str,
    engine_version: str,
    packages: List[str],
    accel_enabled: bool = False,
    accel_pre_serve: Optional[List[str]] = None,
    accel_pre_serve_master: Optional[List[str]] = None,
    accel_pre_serve_client: Optional[List[str]] = None,
    kv_disk_offload_path: Optional[str] = None,
    analyzer_preamble: Optional[str] = None,
    engine_pre_start: Optional[List[str]] = None,
) -> str:
    """生成 start_command.sh 内容。简洁执行脚本。

    Args:
        argv: 引擎命令 argv(含 accel 参数——accel.engine_config 已并入 engine_config_traces)。
        env_traces: env 逐项 trace。
        system_setup: 系统级设置。
        engine: 引擎名称,传给 wings-accel install.py。
        engine_version: 引擎版本,传给 wings-accel install.py。
        packages: 选中 scheme 声明的 pip 依赖(name:version),传给 install.py ``--config``。
        accel_enabled: wings-accel 是否真启用(``AccelResult.enabled``)。仅 True 时渲染
            runtime patch 安装段;False(未开/模块缺席)→ 不加,非 accel 路径零影响。
        accel_pre_serve: KV 存储后端 pre-serve 段(所有节点);None/空 → 不渲染。
        accel_pre_serve_master: KV 存储后端 pre-serve 段(仅 master);None/空 → 不渲染。
        accel_pre_serve_client: KV 存储后端 pre-serve 段(仅 client);None/空 → 不渲染。
        kv_disk_offload_path: KV 磁盘卸载实际路径(accel 产出);None(无磁盘卸载)→ 不渲染
            残留清理段。清理 vllm serve 前的卸载目录残留,保证重启后占用不超规划容量。
        analyzer_preamble: log_analyzer 进度监控 shell 片段;None → 不注入。
            在 env export 之前插入,确保分析器在引擎启动前就开始监控日志。
            启动后台分析器进程并注册 trap 清理。
        engine_pre_start: extension 生成的引擎专属启动前片段。公共渲染层只保证
            它位于通用 env/accel 准备之后、唯一引擎生命周期之前，不解释内容。
    """
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        # shell 日志辅助函数: 输出符合 log-format 规范的日志行(所有脚本通用)。
        # 格式: 时间 [LEVEL] WINGS-CONTROL [组件#函数:行号] 消息
        # 无条件定义,使 worker 节点(无 analyzer_preamble)也能使用 _wings_log。
        "_wings_log() {",
        '    local level="$1"; shift',
        '    local msg="$*"',
        "    local ts",
        '    ts=$(date "+%Y-%m-%d %H:%M:%S.%3N")',
        '    echo "$ts [$level] WINGS-CONTROL [wings-launcher#start_command:0] $msg"',
        "}",
        "",
    ]

    # log_analyzer 进度监控(在 env export 之前,与旧版组装顺序一致)
    if analyzer_preamble:
        lines += [
            analyzer_preamble,
            "",
            # stdout 重定向到 engine.log(供 log_analyzer tail -F 跟踪)
            # 与旧版 wings_entry.py:1899-1911 逻辑一致:
            # 1) mkdir 确保日志目录存在
            # 2) PYTHONUNBUFFERED 确保引擎 ready 消息立即到达 engine.log(不卡在 8KB 缓冲区)
            # 3) tee 管道:完整日志→engine-full.log,过滤健康检查/调度噪声→engine.log
            f"mkdir -p {settings.ENGINE_LOG_DIR}",
            "export PYTHONUNBUFFERED=1",
            f"exec > >(tee -a {settings.ENGINE_FULL_LOG_FILE}"
            " | grep --line-buffered -vE"
            " '\"GET\\s+/(health|metrics)\\s|\\b(Prefill|Decode) batch\\b'"
            f" | tee -a {settings.ENGINE_LOG_FILE}) 2>&1",
            "",
        ]

    # recipe、特性和 wings-accel 环境变量均已由 resolver 合并进 env_traces。
    env_lines = _render_env_section(env_traces)
    if env_lines:
        lines.extend(env_lines)
        lines.append("")

    # system_setup 恒以注释形式渲染，不在启动脚本中执行。
    setup_lines = _render_system_setup_comments(system_setup)
    if setup_lines:
        lines.extend(setup_lines)

    # wings-accel runtime patch 安装段(仅 accel 真启用时)
    if accel_enabled:
        lines.extend(_render_accel_install_preamble(engine, engine_version, packages))

    # KV 存储后端(memcache/mooncake)pre-serve 段:vllm serve 前生成配置 / 起 daemon。
    # 非 KV 后端路径 → 两段皆空 → _render_accel_pre_serve_section 返回 [](零影响)。
    pre_serve_lines = _render_accel_pre_serve_section(accel_pre_serve, accel_pre_serve_master, accel_pre_serve_client)
    if pre_serve_lines:
        lines.extend(pre_serve_lines)

    # KV 磁盘卸载残留清理(仅 disk 开启):vllm serve 前清空卸载目录,保证重启后占用不超规划容量
    lines.extend(_render_kv_disk_cleanup_section(kv_disk_offload_path))


    # MindIE 等结构化配置引擎在这里准备外部 config、固定 ranktable 和动态环境。
    # extension 不能自行启动后台进程；进程回收和 analyzer cleanup 仍由公共层持有。
    if engine_pre_start:
        lines.extend(engine_pre_start)
    # 后台化引擎进程(而非 exec 替换 shell),使 trap cleanup_analyzer 保持有效。
    # exec 会替换 shell 进程导致 trap 失效:引擎退出时 cleanup 无法触发,
    # log_analyzer 成为孤儿进程。后台化 + wait 保持 shell 存活,trap 正常工作,
    # 引擎退出后 shell 执行 cleanup → kill log_analyzer → 写 early-fail 进度。
    lines += [
        shlex.join(argv) + " &",
        "ENGINE_PID=$!",
        '_wings_log INFO "engine started, PID=$ENGINE_PID"',
        'wait "$ENGINE_PID"',
        "ENGINE_EXIT_CODE=$?",
        'exit "$ENGINE_EXIT_CODE"',
        "",
    ]
    return "\n".join(lines)


def _render_plan_repro_sh(
    resolved: ResolvedConfig,
    start_content: str,
    trace_comment_lines: List[str],
) -> str:
    """为结构化启动计划在实际脚本上补充来源注释。

    不能把 MindIE 的嵌套配置反向渲染成 ``--flag``。因此直接复用已经生成的
    start 内容，只在 shebang 后插入注释，保证 pre-start、daemon argv 与公共
    后台等待生命周期完全一致。
    """
    lines = start_content.splitlines()
    header = [
        "# ─── Reproducibility Script ───",
        f"# Generated from: {', '.join(resolved.source_files)}",
        f"# Hardware: {resolved.hardware.hardware_family}",
        f"# Engine: {resolved.engine} v{resolved.engine_version.resolved}",
        f"# Topology: {resolved.topology.value}",
        "",
        *trace_comment_lines,
        "",
    ]
    if not lines:
        return "\n".join(header) + "\n"
    return "\n".join([lines[0], *header, *lines[1:]]) + "\n"


def _render_repro_sh(resolved: ResolvedConfig) -> str:
    """生成 repro.sh 内容。可移植复现脚本,含来源注释。

    直接遍历 resolved.engine_config_traces 生成带注释的参数行,
    不从 argv 字符串反推 key/结构(避免脆弱的反向映射)。
    渲染规则复用 vllm_adapter.render_param_tokens(同一套逻辑,不重复实现)。

    Args:
        resolved: 解析结果。
    """
    lines = [
        "#!/usr/bin/env bash",
        "# ─── Reproducibility Script ───",
        f"# Generated from: {', '.join(resolved.source_files)}",
        f"# Hardware: {resolved.hardware.hardware_family}",
        f"# Engine: {resolved.engine} {resolved.engine_version.resolved}",
        f"# Topology: {resolved.topology.value}",
        "",
        "set -euo pipefail",
        "",
    ]

    # env section with trace comments
    if resolved.env_traces:
        lines.append("# ─── Environment Variables ───")
        for env_key, traced in resolved.env_traces.items():
            if traced.final_value is not None:
                lines.append(f"# source: {traced.source_file} @ {traced.source_path}")
                lines.append(
                    render_env_export(env_key, traced.final_value, allow_unsafe=traced.allow_unsafe)
                )
        lines.append("")

    # KV 存储后端 pre-serve 段(memcache/mooncake);与 start_command.sh 同款渲染。
    pre_serve_lines = _render_accel_pre_serve_section(
        resolved.accel.pre_serve, resolved.accel.pre_serve_master, resolved.accel.pre_serve_client
    )
    if pre_serve_lines:
        lines.extend(pre_serve_lines)

    # KV 磁盘卸载残留清理(与 start_command.sh 同款;repro 复现也需干净基线)
    lines.extend(_render_kv_disk_cleanup_section(resolved.accel.kv_disk_offload_path))

    # system_setup 仅以注释形式渲染。
    setup_lines = _render_system_setup_comments(resolved.system_setup)
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
        lines.append(f"#   {model_cmd}   <- {model_traced.final_layer} ({model_file})")

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
        lines.append(f"#   {rendered_for_comment}   <- {traced.final_layer} ({source_file_name})")

    # 注:accel.engine_config 已作为 strategy_accel 合并层进 engine_config_traces,
    # 上方主循环已渲染并标来源,这里无需重复追加。

    # repro.sh 使用 exec 直接替换进程(无需 trap/cleanup,repro 仅用于复现,无 log_analyzer)
    lines.append("exec " + shlex.join(command_tokens))

    lines.append("")
    return "\n".join(lines)


_MULTI_NODE_BANNER = [
    "# ============================================================================",
    "# MULTI-NODE — RUNTIME INJECTION PENDING (RANK_IP/NODE_IPS are unavailable)",
    "# This is a placeholder script: nodes are loaded and merged, but the current Pod is not selected.",
    "# Rerun wings-ctl in each Pod with RANK_IP/NODE_IPS/MASTER_IP to generate an executable script.",
    "# The argv/env values below contain literal unresolved placeholders and are for review only.",
    "# Do not execute this script directly.",
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
    lines.append('echo "multi_node placeholder script: runtime injection is pending (missing RANK_IP/NODE_IPS); do not execute directly" >&2')
    lines.append("exit 3")
    lines.append("")

    for i, node in enumerate(resolved.nodes or []):
        idx = f" index={node.index}" if node.index is not None else ""
        lines.append(f"# ─── node[{i}] role={node.role}{idx} (source: {node.source_prefix}) ───")
        env_lines = _render_env_section(node.env_traces)
        if env_lines:
            lines.append("#   env (runtime injection pending):")
            lines.extend(f"#     {line}" for line in env_lines)
        setup_lines = _render_system_setup_comments(node.system_setup)
        lines.extend(f"# {line}" if line else "#" for line in setup_lines)
        argv = build_argv(node.engine_config_traces, engine=resolved.engine)
        lines.append("#   argv (runtime injection pending; placeholders are literal):")
        lines.append(f"#     {shlex.join(argv)}")
        lines.append("")
    return "\n".join(lines)


def _render_pd_process_plan(resolved: ResolvedConfig) -> str:
    """从唯一 ``ProcessPlan`` 渲染 single 或 fail-together 脚本。

    Args:
        resolved: ``process_plan`` 非空的 PD 解析结果。

    Returns:
        可执行 bash 脚本文本；每条命令来自结构化 argv 并经 ``shlex.join``。

    Raises:
        ValueError: plan 为空、layout/lifecycle 不受支持或进程集合为空。
    """
    plan = resolved.process_plan
    if plan is None or not plan.processes:
        raise ValueError("PD rendering requires a non-empty process_plan")
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    if plan.lifecycle == "single":
        process = plan.processes[0]
        lines.extend(_render_env_section(process.env_traces))
        if process.env_traces:
            lines.append("")
        lines.append("exec " + shlex.join(process.argv))
        lines.append("")
        return "\n".join(lines)
    if plan.lifecycle != "fail_together":
        raise ValueError(f"Unknown PD lifecycle: {plan.lifecycle!r}")

    lines.extend(
        [
            "pids=()",
            "terminate_children() {",
            "  local pid",
            '  for pid in "${pids[@]}"; do',
            '    kill -TERM "$pid" 2>/dev/null || true',
            "  done",
            "}",
            "trap terminate_children TERM INT",
            "",
        ]
    )
    for process in plan.processes:
        lines.append(f"# process[{process.process_index}] rank={process.dp_rank}")
        lines.append("(")
        lines.extend(f"  {line}" for line in _render_env_section(process.env_traces))
        lines.append("  exec " + shlex.join(process.argv))
        lines.append(") &")
        lines.append('pids+=("$!")')
        lines.append("")
    lines.extend(
        [
            "status=0",
            "set +e",
            'wait -n "${pids[@]}"',
            "status=$?",
            "set -e",
            "terminate_children",
            'for pid in "${pids[@]}"; do',
            '  wait "$pid" 2>/dev/null || true',
            "done",
            "if (( status == 0 )); then status=1; fi",
            'exit "$status"',
            "",
        ]
    )
    return "\n".join(lines)


def build_scripts(
    resolved: ResolvedConfig,
    output_dir: Path,
) -> Tuple[Path, Path]:
    """生成 start_command.sh 和 repro.sh 并写入 output_dir。

    四条路径:
    - PD ``process_plan`` 非空 → 按 single/fail-together 生命周期渲染可执行脚本。
    - multi_node 占位(``resolved.nodes`` 非空,无运行时上下文)→ 占位脚本(无 exec,exit 3)。
    - multi_node 已注入(topology==MULTI_NODE 且已选 node)→ 渲染可执行脚本。
    - standalone → 渲染可执行脚本。

    ``system_setup.commands`` 在所有路径均仅以注释形式保留，不会被脚本执行。

    Returns:
        (start_command_path, repro_path) 元组。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    start_path = output_dir / "start_command.sh"
    repro_path = output_dir / "repro.sh"

    if resolved.process_plan:
        pd_script = _render_pd_process_plan(resolved)
        start_path.write_text(pd_script, encoding="utf-8")
        start_path.chmod(0o755)
        repro_path.write_text(pd_script, encoding="utf-8")
        repro_path.chmod(0o755)
        return start_path, repro_path

    if resolved.nodes:
        # multi_node 占位:两件产物同为占位脚本,显式阻断误执行。
        # 占位脚本不 exec,也不追加 accel 产出。
        placeholder = _render_multi_node_placeholder(resolved)
        start_path.write_text(placeholder, encoding="utf-8")
        start_path.chmod(0o755)
        repro_path.write_text(placeholder, encoding="utf-8")
        repro_path.chmod(0o755)
        return start_path, repro_path

    # advanced_features.json(使能状态单一真相源)在脚本生成阶段写入共享卷,
    # health 接口 /v1/startup/accel 读它回显页面(对齐老仓库 wings_entry 时机)。
    _write_advanced_features_json(resolved)

    # registry 是 CLI、正式渲染和摘要共用的唯一 adapter 分发点。公共层只消费
    # 启动计划，不判断 MindIE，也不读取其 engine_state。
    launch_plan = build_launch_plan(resolved)
    argv = launch_plan.argv
    analyzer_preamble = _build_analyzer_preamble(resolved)
    start_content = _render_start_command_sh(
        argv,
        resolved.env_traces,
        resolved.system_setup,
        engine=resolved.engine,
        # install preamble 使用实际引擎版本(优先 requested,回退 resolved)。
        engine_version=resolved.engine_version.requested or resolved.engine_version.resolved,
        packages=resolved.accel.packages,
        accel_enabled=resolved.accel.enabled,
        accel_pre_serve=resolved.accel.pre_serve,
        accel_pre_serve_master=resolved.accel.pre_serve_master,
        accel_pre_serve_client=resolved.accel.pre_serve_client,
        kv_disk_offload_path=resolved.accel.kv_disk_offload_path,
        analyzer_preamble=analyzer_preamble,
        engine_pre_start=launch_plan.pre_start_lines,
    )
    start_path.write_text(start_content, encoding="utf-8")
    start_path.chmod(0o755)

    if launch_plan.repro_trace_lines is not None:
        repro_content = _render_plan_repro_sh(
            resolved,
            start_content,
            launch_plan.repro_trace_lines,
        )
    else:
        repro_content = _render_repro_sh(resolved)
    repro_path.write_text(repro_content, encoding="utf-8")
    repro_path.chmod(0o755)

    return start_path, repro_path
