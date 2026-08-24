"""EngineParamValidator:启动前的参数支持性校验(只告警,不改参)。

运行位置:配置全部合并完成后、脚本落盘前。
校验对象:最终会渲染到命令行的 ``--flag``。
失败策略:只记录 warning 和审计信息,不阻断启动。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from wings_ctl.core.models import EngineVersion, ParamValidationResult, ResolvedConfig, TracedValue
from wings_ctl.engines.extension import get_engine_extension
from wings_ctl.engines.vllm_adapter import MODEL_KEYS, render_param_tokens
from wings_ctl.loaders.locator import resolve_version_dir

logger = logging.getLogger(__name__)


def _resolve_supported_params_path(
    config_root: Path,
    engine: str,
    engine_version: EngineVersion,
) -> Path:
    """定位该(引擎,版本)对应的 ``supported_params.txt`` 路径。

    有版本层引擎(sglang / vllm-ascend)→ ``engines/{engine}/{version_dir}/supported_params.txt``;
    无版本层引擎(vllm)→ ``engines/{engine}/supported_params.txt``。

    Args:
        config_root: 配置根目录(含 ``engines/`` 子目录)。
        engine: 引擎名(如 ``"vllm"`` / ``"sglang"``)。
        engine_version: 版本解析结果。

    Returns:
        ``supported_params.txt`` 的路径(不保证存在,存在性由加载方判定)。
    """
    engine_root = config_root / "engines" / engine
    if engine_version.has_version_dir and engine_version.resolved:
        return resolve_version_dir(engine_root, engine_version.resolved) / "supported_params.txt"
    return engine_root / "supported_params.txt"


def _load_supported_params(path: Path) -> Optional[Set[str]]:
    """把 ``supported_params.txt`` 解析成 flag 集合(去注释/空行,取 ``--long-option``)。

    格式:``#`` 开头注释头 + 每行一个 ``--long-option``(wings-config 产出)。复合参数
    (如 ``--kv-transfer-config``)文件里本就是顶层名,原样入集。

    Args:
        path: 清单路径。

    Returns:
        flag 集合(如 ``{"--max-model-len", ...}``)。
        文件不存在、空文件或全注释时返回 ``None``。
    """
    if not path.is_file():
        return None
    flags: Set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("--"):
            flags.add(stripped.split()[0])  # 取首 token,防说明性尾随内容
    return flags or None


def collect_unsupported(
    engine_config_traces: Dict[str, TracedValue],
    supported: Set[str],
) -> List[Dict[str, Any]]:
    """对一份 ``engine_config_traces`` 做参数支持校验。

    Args:
        engine_config_traces: 参数名(渲染名)→ TracedValue。
        supported: ``_load_supported_params`` 产出的支持 flag 集合。

    Returns:
        unsupported 项列表;每项 ``{param, rendered_as, final_layer, source_file, source_path}``。
    """
    unsupported: List[Dict[str, Any]] = []
    for key, traced in engine_config_traces.items():
        if key in MODEL_KEYS:  # model / model_path 在命令头渲染,不在这里校验
            continue
        tokens = render_param_tokens(key, traced.final_value)
        if not tokens:
            continue
        rendered_flag = tokens[0]
        if not rendered_flag.startswith("--"):
            continue
        # 点号嵌套配置以 --kernel-config.field=value 形式渲染,而支持清单只记录
        # 顶层 CLI option --kernel-config;校验时去掉点号后的路径和值。
        supported_flag = rendered_flag.split(".", 1)[0]
        if supported_flag not in supported:
            unsupported.append(
                {
                    "param": key,
                    "rendered_as": rendered_flag,
                    "final_layer": traced.final_layer,
                    "source_file": traced.source_file,
                    "source_path": traced.source_path,
                }
            )
    return unsupported


def _node_label(role: str, index: Optional[int]) -> str:
    """node 标识(供 audit/日志区分是哪个节点):``role`` 或 ``role[index]``。"""
    return f"{role}[{index}]" if index is not None else role


def _collect_and_warn(
    engine_config_traces: Dict[str, TracedValue],
    supported: Set[str],
    engine: str,
    node_label: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """收集 unsupported 并逐条输出 warning。

    Args:
        engine_config_traces: 一份 engine_config traces(顶层或某个 node)。
        supported: 当前引擎允许的 flag 集合(如 ``{"--host", "--port"}``)。
        engine: 引擎名,仅用于日志文案。
        node_label: multi_node 节点标签(如 ``"head"`` / ``"worker[1]"``);
            为 None 时按 standalone 形态输出(结果项不带 ``node`` 字段)。

    Returns:
        unsupported 列表。multi_node 场景下每项会附加 ``node`` 字段。
    """

    unsupported = collect_unsupported(engine_config_traces, supported)
    node_hint = f"[node={node_label}]" if node_label else ""
    for item in unsupported:
        if node_label is not None:
            item["node"] = node_label
        logger.warning(
            "EngineParamValidator: %s参数 '%s'(渲染为 %s)不在 %s 支持清单中(warn-only,不删参);来源 %s#%s",
            node_hint,
            item["param"],
            item["rendered_as"],
            engine,
            item["source_file"],
            item["source_path"],
        )
    return unsupported


def validate_engine_params(resolved: ResolvedConfig, config_root: Path) -> None:
    """执行参数支持校验并写入 ``resolved.param_validation``。

    - standalone: 校验顶层 ``engine_config_traces``;
    - multi_node: 逐个 node 校验并汇总结果。

    Args:
        resolved: 解析结果(读 ``engine`` / ``engine_version`` / 顶层或 per-node ``engine_config_traces``,
            写 ``param_validation``)。
        config_root: 配置根目录(定位清单用)。

    Returns:
        None(副作用:设置 ``resolved.param_validation``)。
    """
    # 结构化配置引擎由 extension 校验自身的完整领域计划。未注册 validator 的
    # argv 引擎继续走 supported_params.txt，PD 逐 process 逻辑保持不变。
    extension_validator = get_engine_extension(resolved.engine).validator
    if extension_validator is not None:
        resolved.param_validation = extension_validator(resolved)
        return

    path = _resolve_supported_params_path(config_root, resolved.engine, resolved.engine_version)
    supported = _load_supported_params(path)

    if supported is None:
        # 缺清单时只告警并跳过,不阻塞启动。
        logger.warning(
            "EngineParamValidator: supported_params 清单缺失/为空(%s);按 warn-skip 跳过参数校验,不阻塞启动。",
            path,
        )
        resolved.param_validation = ParamValidationResult(
            supported_params_file=None,
            status="skipped_missing_file",
            unsupported=[],
        )
        if resolved.process_plan:
            for process in resolved.process_plan.processes:
                process.param_validation = ParamValidationResult(
                    supported_params_file=None,
                    status="skipped_missing_file",
                    unsupported=[],
                )
        return

    if resolved.process_plan:  # PD:逐 process 校验最终 native flags。
        unsupported = []
        for process in resolved.process_plan.processes:
            process_unsupported = _collect_and_warn(
                process.engine_config_traces,
                supported,
                resolved.engine,
                node_label=f"process[{process.process_index}] rank={process.dp_rank}",
            )
            for item in process_unsupported:
                item["process_index"] = process.process_index
                item["dp_rank"] = process.dp_rank
            process.param_validation = ParamValidationResult(
                supported_params_file=str(path),
                status="checked",
                unsupported=process_unsupported,
            )
            unsupported.extend(process_unsupported)
        logger.info(
            "EngineParamValidator: 校验完成(PD) engine=%s file=%s processes=%d unsupported=%d",
            resolved.engine,
            path,
            len(resolved.process_plan.processes),
            len(unsupported),
        )
    elif resolved.nodes:  # multi_node:顶层空,逐 node 校验(全 node 共用同一份清单)
        unsupported: List[Dict[str, Any]] = []
        for node in resolved.nodes:
            unsupported.extend(
                _collect_and_warn(
                    node.engine_config_traces,
                    supported,
                    resolved.engine,
                    node_label=_node_label(node.role, node.index),
                )
            )
        logger.info(
            "EngineParamValidator: 校验完成(multi_node)engine=%s file=%s nodes=%d unsupported=%d",
            resolved.engine,
            path,
            len(resolved.nodes),
            len(unsupported),
        )
    else:  # standalone:校验顶层 traces
        unsupported = _collect_and_warn(resolved.engine_config_traces, supported, resolved.engine)
        logger.info(
            "EngineParamValidator: 校验完成 engine=%s file=%s unsupported=%d",
            resolved.engine,
            path,
            len(unsupported),
        )

    resolved.param_validation = ParamValidationResult(
        supported_params_file=str(path),
        status="checked",
        unsupported=unsupported,
    )
