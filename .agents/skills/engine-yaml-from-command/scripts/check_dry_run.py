#!/usr/bin/env python3
"""Compare generated YAML engine parameters with the source launch command."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

import yaml


ENGINES = ("vllm", "vllm-ascend", "sglang")
SCENARIOS = ("standalone", "multi_node", "pd_disaggregation")
DEFAULT_SCENARIOS = ("standalone", "multi_node", "pd_disaggregation")


class DryRunMismatch(ValueError):
    """The YAML and launch command do not describe the same parameters."""


def kebab(name: str) -> str:
    return "--" + name.replace("_", "-")


def scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return str(value)


def normalize_value(value: str) -> str:
    """Ignore shell/YAML serialization differences for JSON-valued arguments."""
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value
    if isinstance(parsed, (dict, list)):
        return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
    return value


def add_argument(result: dict[str, str], flag: str, value: Any = "true") -> None:
    if not flag.startswith("--"):
        raise DryRunMismatch(f"invalid flag {flag!r}")
    result[flag] = scalar(value)


def render_command(arguments: dict[str, str]) -> str:
    """Render parsed arguments as a copyable shell command."""
    parts: list[str] = []
    for flag, value in arguments.items():
        parts.append(flag)
        if value != "true":
            parts.append(shlex.quote(value))
    return " ".join(parts)


def parse_tokens(tokens: list[str], engine: str) -> dict[str, str]:
    """Parse one engine command into flag/value pairs."""
    if engine in {"vllm", "vllm-ascend"}:
        try:
            start = tokens.index("serve") + 1
        except ValueError as exc:
            raise DryRunMismatch("command does not contain 'vllm serve'") from exc
    else:
        start = next((i for i, token in enumerate(tokens) if token == "sglang"), None)
        if start is None:
            raise DryRunMismatch("command does not contain 'sglang'")
        start += 1

    result: dict[str, str] = {}
    positional = tokens[start:]
    index = 0
    if engine in {"vllm", "vllm-ascend"} and positional and not positional[0].startswith("-"):
        add_argument(result, "--model", positional[0])
        index = 1
    while index < len(positional):
        token = positional[index]
        if not token.startswith("--"):
            index += 1
            continue
        if "=" in token:
            flag, value = token.split("=", 1)
            add_argument(result, flag, value)
            index += 1
            continue
        if index + 1 < len(positional) and not positional[index + 1].startswith("--"):
            add_argument(result, token, positional[index + 1])
            index += 2
        else:
            add_argument(result, token)
            index += 1
    return result


def command_env(text: str) -> dict[str, str]:
    """Parse explicit ``export KEY=value`` assignments from a launch script."""
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("export "):
            continue
        assignment = line[len("export ") :].strip()
        try:
            tokens = shlex.split(assignment, comments=True, posix=True)
        except ValueError as exc:
            raise DryRunMismatch(f"invalid environment export: {line!r}") from exc
        for token in tokens:
            if "=" not in token:
                raise DryRunMismatch(f"environment export lacks a value: {token!r}")
            key, value = token.split("=", 1)
            if not key:
                raise DryRunMismatch(f"environment export has an empty name: {token!r}")
            result[key] = value
    return result


def yaml_environment(config: dict[str, Any]) -> dict[str, str]:
    """Return YAML ``env`` values in the same scalar form as shell exports."""
    env = config.get("env", {})
    if env is None:
        return {}
    if not isinstance(env, dict):
        raise DryRunMismatch("engine_config.env must be a mapping")
    return {str(key): scalar(value) for key, value in env.items()}


def compare_environment(expected: dict[str, str], actual: dict[str, str], label: str) -> list[str]:
    """Compare YAML environment variables with explicit command exports."""
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    different = sorted(
        key for key in set(expected) & set(actual)
        if normalize_value(expected[key]) != normalize_value(actual[key])
    )
    details = [f"{label} env: {'OK' if not (missing or extra or different) else '异常'}"]
    for key in sorted(set(expected) & set(actual)):
        if key not in different:
            details.append(f"  OK       {key}: {expected[key]!r}")
    for key in missing:
        details.append(f"  缺失     {key}: YAML={expected[key]!r}")
    for key in extra:
        details.append(f"  多余     {key}: command={actual[key]!r}")
    for key in different:
        details.append(
            f"  不一致   {key}: YAML={expected[key]!r}, command={actual[key]!r}"
        )
    if missing or extra or different:
        raise DryRunMismatch("\\n".join(details))
    return details


def command_tokens(text: str) -> list[str]:
    logical_lines: list[str] = []
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("export "):
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
            continue
        logical_lines.append(current + line)
        current = ""
    if current:
        logical_lines.append(current)
    for line in logical_lines:
        try:
            tokens = shlex.split(line, comments=True, posix=True)
        except ValueError:
            continue
        if "vllm" in tokens and "serve" in tokens:
            return tokens[tokens.index("vllm") :]
        if "sglang" in tokens:
            return tokens[tokens.index("sglang") :]
    raise DryRunMismatch("no supported engine launch command found")


def iter_engine_configs(strategy: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    configs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    strategy_env = strategy.get("env", {})
    if isinstance(strategy.get("engine_config"), dict):
        configs.append((strategy["engine_config"], strategy_env))
    for role in ("head", "worker"):
        node = strategy.get(role)
        if isinstance(node, dict) and isinstance(node.get("engine_config"), dict):
            configs.append((node["engine_config"], node.get("env", strategy_env)))
    for node in strategy.get("nodes", []) or []:
        if isinstance(node, dict) and isinstance(node.get("engine_config"), dict):
            configs.append((node["engine_config"], node.get("env", strategy_env)))
    return configs


def yaml_configs(data: dict[str, Any], scenario: str) -> list[dict[str, Any]]:
    scenarios = data.get("scenarios", {})
    scenario_data = scenarios.get(scenario, {})
    strategies = scenario_data.get("strategies", {})
    strategy = next(
        (value for value in strategies.values() if isinstance(value, dict) and value.get("default_strategy")),
        next(iter(strategies.values()), {}),
    )
    features = data.get("features", {}) or {}
    feature_args: dict[str, str] = {}
    for feature in features.values():
        if not isinstance(feature, dict):
            continue
        args = feature.get("args", [])
        if not isinstance(args, list):
            continue
        feature_args.update(parse_tokens(["sglang", *args], "sglang"))
    result: list[dict[str, Any]] = []
    for config, strategy_env in iter_engine_configs(strategy):
        values: dict[str, str] = {}
        for key, value in config.items():
            if key == "env":
                continue
            flag = kebab(key)
            if key in {"model_path", "model"}:
                flag = "--model" if key == "model" else "--model-path"
            add_argument(values, flag, value)
        values.update(feature_args)
        environment = config.get("env", strategy_env)
        result.append({"arguments": values, "env": yaml_environment({"env": environment})})
    return result


def compare(
    expected: dict[str, str], actual: dict[str, str], label: str
) -> list[str]:
    # vLLM YAMLs may use a distributable HF/ModelScope ID instead of a
    # machine-local absolute model path. Keep strict comparison for every
    # explicitly represented parameter, including served_model_name.
    comparable_expected = dict(expected)
    comparable_actual = dict(actual)
    if comparable_actual.get("--model", "").startswith("/"):
        comparable_expected.pop("--model", None)
        comparable_actual.pop("--model", None)

    missing = sorted(set(comparable_expected) - set(comparable_actual))
    extra = sorted(set(comparable_actual) - set(comparable_expected))
    different = sorted(
        key
        for key in set(comparable_expected) & set(comparable_actual)
        if normalize_value(comparable_expected[key]) != normalize_value(comparable_actual[key])
    )
    details = [f"{label}: {'OK' if not (missing or extra or different) else '异常'}"]
    for key in sorted(set(comparable_expected) & set(comparable_actual)):
        if key not in different:
            details.append(f"  OK       {key}: {comparable_expected[key]!r}")
    for key in missing:
        details.append(f"  缺失     {key}: YAML={comparable_expected[key]!r}")
    for key in extra:
        details.append(f"  多余     {key}: command={comparable_actual[key]!r}")
    for key in different:
        details.append(
            f"  不一致   {key}: YAML={comparable_expected[key]!r}, "
            f"command={comparable_actual[key]!r}"
        )
    if missing or extra or different:
        raise DryRunMismatch("\n".join(details))
    return details


def check_default_model(
    yaml_path: Path,
    engine: str,
    engine_version: str,
    hardware_profile: str,
    gpu_count: int,
    vram_per_gpu_gb: int,
) -> list[str]:
    """Validate a generated default_model.yaml without a launch command."""
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DryRunMismatch(f"cannot read default model YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise DryRunMismatch("default_model.yaml must contain a mapping")
    if set(data) != {"hardware", "engine", "scenarios"}:
        raise DryRunMismatch("default_model.yaml must contain only hardware, engine, scenarios")
    hardware = data.get("hardware")
    engine_data = data.get("engine")
    scenarios = data.get("scenarios")
    if not isinstance(hardware, dict) or not isinstance(engine_data, dict) or not isinstance(scenarios, dict):
        raise DryRunMismatch("hardware, engine and scenarios must be mappings")
    expected_vram = gpu_count * vram_per_gpu_gb
    if hardware.get("gpu_count") != gpu_count:
        raise DryRunMismatch(f"hardware.gpu_count: expected {gpu_count}, got {hardware.get('gpu_count')!r}")
    if hardware.get("vram_gb") != expected_vram:
        raise DryRunMismatch(f"hardware.vram_gb: expected {expected_vram}, got {hardware.get('vram_gb')!r}")
    if engine_data.get("name") != engine or engine_data.get("version") != engine_version:
        raise DryRunMismatch(
            f"engine mismatch: expected {engine} {engine_version}, "
            f"got {engine_data.get('name')} {engine_data.get('version')}"
        )
    if len(scenarios) != len(DEFAULT_SCENARIOS) or set(scenarios) != set(DEFAULT_SCENARIOS):
        raise DryRunMismatch("scenarios must contain standalone, multi_node and pd_disaggregation")
    report = [f"default_model: {yaml_path}", f"hardware profile: {hardware_profile}"]
    for scenario in DEFAULT_SCENARIOS:
        scenario_data = scenarios[scenario]
        if not isinstance(scenario_data, dict):
            raise DryRunMismatch(f"scenarios.{scenario} must be a mapping")
        strategies = scenario_data.get("strategies")
        if not isinstance(strategies, dict):
            raise DryRunMismatch(f"scenarios.{scenario}.strategies must be a mapping")
        defaults = [value for value in strategies.values() if isinstance(value, dict) and value.get("default_strategy") is True]
        if len(defaults) != 1:
            raise DryRunMismatch(f"scenarios.{scenario} must have exactly one default_strategy")
        strategy = defaults[0]
        if scenario == "standalone":
            configs = [strategy.get("engine_config")]
        elif scenario == "multi_node":
            configs = [strategy.get(role, {}).get("engine_config") for role in ("head", "worker")]
        else:
            configs = [node.get("engine_config") for node in strategy.get("nodes", []) if isinstance(node, dict)]
            roles = [node.get("role") for node in strategy.get("nodes", []) if isinstance(node, dict)]
            if "prefill" not in roles or "decode" not in roles:
                raise DryRunMismatch("scenarios.pd_disaggregation must contain prefill and decode nodes")
        if not configs or any(not isinstance(config, dict) for config in configs):
            raise DryRunMismatch(f"scenarios.{scenario} has incomplete engine_config")
        for config in configs:
            for key in ("tensor_parallel_size",):
                if key in config and config[key] <= 0:
                    raise DryRunMismatch(f"scenarios.{scenario}.{key} must be positive")
        report.append(f"{scenario}: OK ({len(configs)} engine configs)")
    report.append("OK: default_model dry-run checks passed")
    return report


def check(yaml_path: Path, command_paths: list[Path], engine: str, scenario: str) -> list[str]:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    configs = yaml_configs(data, scenario)
    if not configs:
        raise DryRunMismatch("YAML contains no engine_config for the requested scenario")
    command_texts = [path.read_text(encoding="utf-8") for path in command_paths]
    commands = [parse_tokens(command_tokens(text), engine) for text in command_texts]
    environments = [command_env(text) for text in command_texts]
    if len(configs) != len(commands):
        raise DryRunMismatch(
            f"YAML has {len(configs)} engine configs but commands provide {len(commands)}"
        )
    report: list[str] = []
    for index, (expected, actual, environment) in enumerate(zip(configs, commands, environments)):
        label = f"node[{index}]"
        expected_arguments = expected["arguments"]
        expected_environment = expected["env"]
        report.extend(
            [
                f"[{label}] YAML 重建命令:",
                f"  {render_command(expected_arguments)}",
                f"[{label}] 原始启动命令:",
                f"  {render_command(actual)}",
            ]
        )
        try:
            report.extend(compare(expected_arguments, actual, label))
            report.extend(compare_environment(expected_environment, environment, label))
        except DryRunMismatch as exc:
            raise DryRunMismatch("\n".join(report + [str(exc)])) from exc
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, choices=ENGINES)
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--command-file", action="append", type=Path)
    parser.add_argument("--default-model", action="store_true")
    parser.add_argument("--engine-version")
    parser.add_argument("--hardware-profile")
    parser.add_argument("--gpu-count", type=int)
    parser.add_argument("--vram-per-gpu-gb", type=int)
    parser.add_argument("yaml_path", type=Path)
    args = parser.parse_args()
    try:
        if args.default_model:
            required = (args.engine_version, args.hardware_profile, args.gpu_count, args.vram_per_gpu_gb)
            if any(value is None for value in required):
                parser.error("--default-model requires --engine-version, --hardware-profile, --gpu-count and --vram-per-gpu-gb")
            report = check_default_model(
                args.yaml_path, args.engine, args.engine_version, args.hardware_profile,
                args.gpu_count, args.vram_per_gpu_gb,
            )
        else:
            if not args.scenario or not args.command_file:
                parser.error("normal dry-run requires --scenario and at least one --command-file")
            report = check(args.yaml_path, args.command_file, args.engine, args.scenario)
    except (OSError, yaml.YAMLError, DryRunMismatch) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(*report, sep="\n")
    print(f"OK: dry-run parameters match {args.yaml_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
