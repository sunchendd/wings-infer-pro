#!/usr/bin/env python3
"""校验 engine-yaml-from-command 生成的普通模型 YAML 结构。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - depends on the host environment
    raise SystemExit("error: PyYAML is required to run validate_yaml.py") from exc


ENGINES = ("vllm", "vllm-ascend", "sglang")
SCENARIOS = ("standalone", "multi_node", "pd_disaggregation")
TOP_LEVEL_ORDER = (
    "upstream_sources",
    "model",
    "hardware_profile",
    "features",
    "scenarios",
)
BLOCK_COMMANDS_RE = re.compile(r"^\s+commands:\s*(?:#.*)?$")


class ValidationError(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a Wings Control model YAML generated from commands."
    )
    parser.add_argument("--engine", required=True, choices=ENGINES)
    parser.add_argument("--scenario", required=True, choices=SCENARIOS)
    parser.add_argument("yaml_path", type=Path)
    parser.add_argument(
        "--reasoning-registry",
        type=Path,
        help="Path to the reasoning parser registry when features.reasoning is present.",
    )
    return parser.parse_args()


def require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must be a mapping")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"{path} must be a list")
    return value


def validate_top_level(data: dict[str, Any]) -> None:
    required = {"upstream_sources", "model", "hardware_profile", "scenarios"}
    missing = required - data.keys()
    if missing:
        raise ValidationError(f"missing top-level keys: {', '.join(sorted(missing))}")

    unknown = set(data) - set(TOP_LEVEL_ORDER)
    if unknown:
        raise ValidationError(f"unknown top-level keys: {', '.join(sorted(unknown))}")

    positions = [TOP_LEVEL_ORDER.index(key) for key in data]
    if positions != sorted(positions):
        raise ValidationError(
            "top-level key order must be upstream_sources, model, "
            "hardware_profile, optional features, scenarios"
        )


def validate_model(data: dict[str, Any]) -> None:
    model = require_mapping(data["model"], "model")
    required = {"name", "provider", "model_id", "min_engine_version", "match", "variant_name"}
    missing = required - model.keys()
    if missing:
        raise ValidationError(f"model is missing: {', '.join(sorted(missing))}")
    matches = require_list(model["match"], "model.match")
    if not matches or not all(isinstance(item, dict) and item.get("name_pattern") for item in matches):
        raise ValidationError("model.match must contain at least one name_pattern")


def validate_hardware(data: dict[str, Any]) -> None:
    hardware = require_mapping(data["hardware_profile"], "hardware_profile")
    required = {"gpu_count", "vram_gb", "multi_node"}
    missing = required - hardware.keys()
    if missing:
        raise ValidationError(
            f"hardware_profile is missing: {', '.join(sorted(missing))}"
        )
    if not isinstance(hardware["gpu_count"], int) or hardware["gpu_count"] <= 0:
        raise ValidationError("hardware_profile.gpu_count must be a positive integer")
    if not isinstance(hardware["vram_gb"], int) or hardware["vram_gb"] < 0:
        raise ValidationError("hardware_profile.vram_gb must be a non-negative integer")
    if not isinstance(hardware["multi_node"], bool):
        raise ValidationError("hardware_profile.multi_node must be a boolean")


def validate_features(data: dict[str, Any]) -> None:
    if "features" not in data:
        return
    features = require_mapping(data["features"], "features")
    for name, feature in features.items():
        feature_map = require_mapping(feature, f"features.{name}")
        if "args" in feature_map:
            args = require_list(feature_map["args"], f"features.{name}.args")
            if not all(isinstance(arg, str) for arg in args):
                raise ValidationError(f"features.{name}.args must contain only strings")


def parser_from_args(args: list[Any]) -> str | None:
    for index, value in enumerate(args[:-1]):
        if value == "--reasoning-parser":
            parser = args[index + 1]
            if not isinstance(parser, str) or not parser:
                raise ValidationError("features.reasoning parser must be a non-empty string")
            return parser
    raise ValidationError("features.reasoning.args must contain --reasoning-parser and its value")


def validate_reasoning_registry(data: dict[str, Any], registry_path: Path | None) -> None:
    features = data.get("features")
    if not isinstance(features, dict) or "reasoning" not in features:
        return
    if registry_path is None:
        raise ValidationError("--reasoning-registry is required when features.reasoning is present")
    try:
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValidationError(f"cannot read reasoning registry: {exc}") from exc
    parser = parser_from_args(require_list(features["reasoning"].get("args"), "features.reasoning.args"))
    matches = []
    architectures = require_list(registry.get("architectures"), "reasoning registry architectures")
    for architecture in architectures:
        architecture_map = require_mapping(architecture, "reasoning registry architecture")
        models = architecture_map.get("models")
        if not isinstance(models, dict):
            continue
        for name, config in models.items():
            if name.casefold() == data["model"]["variant_name"].casefold():
                matches.append(
                    require_mapping(
                        config,
                        f"{architecture_map.get('name', '<unnamed>')}.models.{name}",
                    )
                )
    if len(matches) != 1:
        raise ValidationError(
            f"reasoning registry must contain exactly one case-insensitive full match for "
            f"{data['model']['variant_name']!r}; found {len(matches)}"
        )
    entry = matches[0]
    for engine in ("vllm", "vllm_ascend"):
        if entry.get(engine) != parser:
            raise ValidationError(
                f"reasoning registry {engine} parser {entry.get(engine)!r} does not match {parser!r}"
            )


def validate_serialization(text: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        if BLOCK_COMMANDS_RE.match(line):
            raise ValidationError(
                f"line {line_number}: system_setup.commands must use a same-line "
                "flow-style list, for example commands: [source /path/a.sh]"
            )


def validate_runtime_sections(container: dict[str, Any], path: str) -> None:
    if "env" in container:
        require_mapping(container["env"], f"{path}.env")
    if "system_setup" not in container:
        return

    setup = require_mapping(container["system_setup"], f"{path}.system_setup")
    if "commands" in setup:
        commands = require_list(setup["commands"], f"{path}.system_setup.commands")
        if not all(isinstance(command, str) for command in commands):
            raise ValidationError(
                f"{path}.system_setup.commands must contain only strings"
            )
    if "sysctls" in setup:
        require_mapping(setup["sysctls"], f"{path}.system_setup.sysctls")
    if "sysfs_writes" in setup:
        writes = require_list(
            setup["sysfs_writes"], f"{path}.system_setup.sysfs_writes"
        )
        for index, write in enumerate(writes):
            item = require_mapping(
                write, f"{path}.system_setup.sysfs_writes[{index}]"
            )
            if "path" not in item or "value" not in item:
                raise ValidationError(
                    f"{path}.system_setup.sysfs_writes[{index}] must contain "
                    "path and value"
                )


def engine_configs(strategy: dict[str, Any], path: str) -> Iterable[tuple[str, dict[str, Any]]]:
    if "engine_config" in strategy:
        yield f"{path}.engine_config", require_mapping(
            strategy["engine_config"], f"{path}.engine_config"
        )
    for role in ("head", "worker"):
        if role in strategy:
            node = require_mapping(strategy[role], f"{path}.{role}")
            yield f"{path}.{role}.engine_config", require_mapping(
                node.get("engine_config"), f"{path}.{role}.engine_config"
            )
    if "nodes" in strategy:
        for index, node_value in enumerate(require_list(strategy["nodes"], f"{path}.nodes")):
            node = require_mapping(node_value, f"{path}.nodes[{index}]")
            yield f"{path}.nodes[{index}].engine_config", require_mapping(
                node.get("engine_config"), f"{path}.nodes[{index}].engine_config"
            )


def validate_engine_config(engine: str, config: dict[str, Any], path: str) -> None:
    if not config:
        raise ValidationError(f"{path} must not be empty")
    first_key = next(iter(config))
    if first_key != "model":
        raise ValidationError(f"{path}.model must be the first key")

    if engine != "sglang" and any(key in config for key in ("model_path", "tp", "dp", "ep")):
        raise ValidationError(f"{path} contains SGLang parameter names for {engine}")
    if engine == "sglang" and any(
        key in config
        for key in ("tensor_parallel_size", "data_parallel_size", "enable_expert_parallel")
    ):
        raise ValidationError(f"{path} contains vLLM parameter names for SGLang")


def validate_data_parallel_rpc_port(config: dict[str, Any], path: str) -> None:
    if "data_parallel_rpc_port" not in config:
        return
    value = config["data_parallel_rpc_port"]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            f"{path}.data_parallel_rpc_port must be a YAML integer, "
            f"not a script placeholder or quoted value: {value!r}"
        )


def validate_kv_transfer_config(config: dict[str, Any], path: str) -> None:
    transfer = config.get("kv_transfer_config")
    if not isinstance(transfer, dict):
        return
    for key in ("engine_id", "kv_port"):
        if key not in transfer:
            continue
        value = transfer[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(
                f"{path}.kv_transfer_config.{key} must be a YAML integer, "
                f"not a script placeholder or quoted value: {value!r}"
            )


def validate_standalone(strategy: dict[str, Any], path: str) -> None:
    if "engine_config" not in strategy:
        raise ValidationError(f"{path} must contain engine_config directly")
    require_mapping(strategy["engine_config"], f"{path}.engine_config")


def validate_multi_node(strategy: dict[str, Any], path: str) -> None:
    has_pair = "head" in strategy and "worker" in strategy
    has_nodes = isinstance(strategy.get("nodes"), list) and len(strategy["nodes"]) >= 2
    if not (has_pair or has_nodes):
        raise ValidationError(f"{path} must contain head/worker or at least two nodes")


def validate_pd(engine: str, strategy: dict[str, Any], path: str) -> None:
    nodes = require_list(strategy.get("nodes"), f"{path}.nodes")
    roles = []
    indexes: set[tuple[str, Any]] = set()
    for index, node_value in enumerate(nodes):
        node_path = f"{path}.nodes[{index}]"
        node = require_mapping(node_value, node_path)
        role = node.get("role")
        if role not in {"prefill", "decode"}:
            raise ValidationError(f"{node_path}.role must be prefill or decode")
        roles.append(role)
        if "index" not in node:
            raise ValidationError(f"{node_path}.index is required")
        identity = (role, node.get("index"))
        if identity in indexes:
            raise ValidationError(f"duplicate PD node identity: {identity}")
        indexes.add(identity)

        config = require_mapping(node.get("engine_config"), f"{node_path}.engine_config")
        if engine == "sglang":
            mode = config.get("disaggregation_mode")
            if mode != role:
                raise ValidationError(
                    f"{node_path}.engine_config.disaggregation_mode must equal {role}"
                )
        else:
            transfer = config.get("kv_transfer_config")
            if isinstance(transfer, dict) and "kv_role" in transfer:
                expected = "kv_producer" if role == "prefill" else "kv_consumer"
                if transfer["kv_role"] != expected:
                    raise ValidationError(
                        f"{node_path}.kv_transfer_config.kv_role must be {expected}"
                    )
    if not {"prefill", "decode"}.issubset(roles):
        raise ValidationError(f"{path}.nodes must include prefill and decode")


def validate_scenarios(data: dict[str, Any], engine: str, requested: str) -> None:
    scenarios = require_mapping(data["scenarios"], "scenarios")
    if requested not in scenarios:
        raise ValidationError(f"scenarios.{requested} is missing")

    for scenario_name, scenario_value in scenarios.items():
        if scenario_name not in SCENARIOS:
            raise ValidationError(f"unsupported scenario: {scenario_name}")
        scenario = require_mapping(scenario_value, f"scenarios.{scenario_name}")
        match = require_mapping(scenario.get("match"), f"scenarios.{scenario_name}.match")
        expected_distributed = scenario_name != "standalone"
        if match.get("distributed") is not expected_distributed:
            raise ValidationError(
                f"scenarios.{scenario_name}.match.distributed must be "
                f"{str(expected_distributed).lower()}"
            )

        strategies = require_mapping(
            scenario.get("strategies"), f"scenarios.{scenario_name}.strategies"
        )
        if not strategies:
            raise ValidationError(f"scenarios.{scenario_name}.strategies must not be empty")
        defaults = [
            name
            for name, value in strategies.items()
            if isinstance(value, dict) and value.get("default_strategy") is True
        ]
        if len(defaults) != 1:
            raise ValidationError(
                f"scenarios.{scenario_name} must have exactly one default strategy"
            )

        for strategy_name, strategy_value in strategies.items():
            path = f"scenarios.{scenario_name}.strategies.{strategy_name}"
            strategy = require_mapping(strategy_value, path)
            validate_runtime_sections(strategy, path)
            for role in ("head", "worker"):
                if role in strategy:
                    role_data = require_mapping(strategy[role], f"{path}.{role}")
                    validate_runtime_sections(role_data, f"{path}.{role}")
            if "nodes" in strategy:
                for index, node_value in enumerate(
                    require_list(strategy["nodes"], f"{path}.nodes")
                ):
                    node = require_mapping(node_value, f"{path}.nodes[{index}]")
                    validate_runtime_sections(node, f"{path}.nodes[{index}]")
            if scenario_name == "standalone":
                validate_standalone(strategy, path)
            elif scenario_name == "multi_node":
                validate_multi_node(strategy, path)
            else:
                validate_pd(engine, strategy, path)

            configs = list(engine_configs(strategy, path))
            if not configs:
                raise ValidationError(f"{path} does not contain any engine_config")
            for config_path, config in configs:
                validate_engine_config(engine, config, config_path)
                validate_kv_transfer_config(config, config_path)
                if scenario_name in {"multi_node", "pd_disaggregation"}:
                    validate_data_parallel_rpc_port(config, config_path)


def main() -> int:
    args = parse_args()
    try:
        text = args.yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        root = require_mapping(data, "document")
        validate_serialization(text)
        validate_top_level(root)
        require_list(root["upstream_sources"], "upstream_sources")
        validate_model(root)
        validate_hardware(root)
        validate_features(root)
        validate_reasoning_registry(root, args.reasoning_registry)
        validate_scenarios(root, args.engine, args.scenario)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"OK: {args.yaml_path} ({args.engine}/{args.scenario})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
