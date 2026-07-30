"""Load and validate the public reasoning-parser capability table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class LoadedReasoningTable:
    data: Mapping[str, Any]
    source_path: str


class ReasoningTableError(ValueError):
    """公共 reasoning parser 表缺失或格式错误。"""


def normalize_reasoning_engine(engine: str) -> str:
    """把引擎名称归一化为公共表查询使用的形式。

    公共表历史上可能使用 ``vllm_ascend``，运行时则可能传入
    ``vllm-ascend``；两者必须指向同一个能力配置。
    """
    normalized = str(engine).strip().lower().replace("_", "-")
    return "vllm-ascend" if normalized == "vllm-ascend" else normalized


def _validate_parser_value(value: Any, path: str) -> None:
    """校验单个 parser 配置，避免错误数据进入运行时 argv。

    null 表示该模型/架构不支持，不是 ``args`` 的合法元素；完整对象
    当前允许通过 ``args`` 携带 parser 和 plugin 参数。
    """
    if value is None or isinstance(value, str):
        return
    if not isinstance(value, dict):
        raise ReasoningTableError(f"{path} must be a parser string, mapping, or null")
    args = value.get("args")
    if args is not None and (
        not isinstance(args, list) or not all(isinstance(item, str) for item in args)
    ):
        raise ReasoningTableError(f"{path}.args must be a list of strings")


def validate_reasoning_table(data: Any) -> Mapping[str, Any]:
    """校验公共表的层级结构和 parser 值类型。"""
    if not isinstance(data, dict):
        raise ReasoningTableError("reasoning table root must be a mapping")
    architectures = data.get("architectures")
    if not isinstance(architectures, list):
        raise ReasoningTableError("reasoning table architectures must be a list")
    for index, architecture in enumerate(architectures):
        prefix = f"architectures[{index}]"
        if not isinstance(architecture, dict) or not isinstance(architecture.get("name"), str):
            raise ReasoningTableError(f"{prefix} must contain a string name")
        config = architecture.get("config", {})
        models = architecture.get("models", {})
        if not isinstance(config, dict) or not isinstance(models, dict):
            raise ReasoningTableError(f"{prefix}.config and models must be mappings")
        for engine, value in config.items():
            if not isinstance(engine, str):
                raise ReasoningTableError(f"{prefix}.config engine must be a string")
            _validate_parser_value(value, f"{prefix}.config.{engine}")
        for model, values in models.items():
            if not isinstance(model, str) or not isinstance(values, dict):
                raise ReasoningTableError(f"{prefix}.models entries must map names to mappings")
            for engine, value in values.items():
                if not isinstance(engine, str):
                    raise ReasoningTableError(f"{prefix}.models.{model} engine must be a string")
                _validate_parser_value(value, f"{prefix}.models.{model}.{engine}")
    return data


def load_reasoning_table(config_root: Path) -> LoadedReasoningTable:
    """从配置根目录旁的 docs 目录加载公共表。"""
    path = config_root.parent / "docs/features/reasoning_parser/reason_parser.yaml"
    try:
        if not path.is_file():
            raise FileNotFoundError(f"reasoning parser table not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return LoadedReasoningTable(validate_reasoning_table(data), str(path))
    except ReasoningTableError:
        raise
    except Exception as exc:
        raise ReasoningTableError(f"failed to load reasoning table {path}: {exc}") from exc
