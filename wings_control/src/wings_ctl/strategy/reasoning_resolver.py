"""Resolve public reasoning-parser capability for a deployment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from wings_ctl.loaders.reasoning_table import normalize_reasoning_engine


@dataclass(frozen=True)
class ModelIdentity:
    """保存 CLI 原始名称和模型 YAML 标准变体名，用于公共表匹配。"""
    requested_name: str
    variant_name: str | None = None


@dataclass(frozen=True)
class ReasoningSpec:
    """已标准化的 reasoning parser 启动参数。"""
    args: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class ReasoningResolution:
    """reasoning parser 解析结果。"""
    status: Literal["matched", "unmatched", "invalid"]
    spec: ReasoningSpec | None
    source: str
    match_level: str
    reason: str | None = None
    conflicts: tuple[str, ...] = ()


def build_model_identity(requested_name: str, model_data: Mapping[str, Any] | None = None) -> ModelIdentity:
    """提取 CLI 原始名称和已命中的模型 YAML variant_name。"""
    model = model_data.get("model", {}) if isinstance(model_data, Mapping) else {}
    model = model if isinstance(model, Mapping) else {}
    variant_name = model.get("variant_name")
    if not isinstance(variant_name, str) or not variant_name.strip():
        variant_name = None
    return ModelIdentity(
        requested_name=requested_name.strip(),
        variant_name=variant_name.strip() if variant_name else None,
    )


_MISSING = object()


def _engine_value(values: Mapping[str, Any], canonical_engine: str) -> tuple[Any, str] | object:
    """读取 parser 值，同时保留 YAML 中实际的 engine key。"""
    for key, value in values.items():
        if normalize_reasoning_engine(str(key)) == canonical_engine:
            return value, str(key)
    return _MISSING


def _parser_spec(value: Any, source: str) -> ReasoningSpec | None:
    """把字符串简写或完整对象转换成统一的 parser args。"""
    if value is None:
        return None
    if isinstance(value, str):
        return ReasoningSpec(("--reasoning-parser", value), source)
    if isinstance(value, Mapping):
        args = value.get("args")
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ValueError(f"{source}.args must be a list of strings")
        return ReasoningSpec(tuple(args), source)
    raise ValueError(f"{source} has an invalid parser value")


def resolve_reasoning(
    table: Mapping[str, Any],
    identity: ModelIdentity,
    engine: str,
    *,
    table_source: str = "reason_parser.yaml",
) -> ReasoningResolution:
    """按公共表精确模型配置解析 parser；未命中时不启用。"""
    canonical_engine = normalize_reasoning_engine(engine)
    if canonical_engine not in {"vllm", "vllm-ascend"}:
        return ReasoningResolution("unmatched", None, table_source, "unsupported_engine", "engine not covered")
    try:
        normalized_names = [
            value.casefold()
            for value in (identity.variant_name, identity.requested_name)
            if value
        ]
        for architecture_index, architecture in enumerate(table.get("architectures", [])):
            if not isinstance(architecture, Mapping):
                continue
            models = architecture.get("models", {})
            for model_name, values in models.items():
                if model_name.casefold() not in normalized_names:
                    continue
                engine_result = _engine_value(values, canonical_engine)
                if engine_result is _MISSING:
                    continue
                value, actual_engine_key = engine_result
                if value is None:
                    continue
                source_path = (
                    f"architectures[{architecture_index}]"
                    f".models.{model_name}.{actual_engine_key}"
                )
                return ReasoningResolution(
                    "matched", _parser_spec(value, source_path),
                    table_source, "model",
                )

        return ReasoningResolution("unmatched", None, table_source, "none", "no exact model match")
    except (TypeError, ValueError, KeyError) as exc:
        return ReasoningResolution("invalid", None, table_source, "invalid", str(exc))
