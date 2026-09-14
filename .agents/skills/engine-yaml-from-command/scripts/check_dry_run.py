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
IGNORED_ENV_VARS = frozenset({"ASCEND_RT_VISIBLE_DEVICES"})
RTX_PRO_5000_AUTO_ENV_VARS = frozenset({"NCCL_P2P_LEVEL", "NCCL_SHM_DISABLE"})
DEFAULT_ENABLED_FEATURES = ("tool_calling", "reasoning")
CHAT_TEMPLATE_FLAG = "--chat-template"


class DryRunMismatch(ValueError):
    """The YAML and launch command do not describe the same parameters."""


# vLLM 的 ``cc.*``(pass 配置)顶层前缀是引擎原生**单横线** flag(``-cc.xxx=value``),
# 与其余 ``--`` 双横线长参数不同。封闭枚举,只影响 ``cc.*``,不扩散到其它顶层前缀。
SINGLE_DASH_TOP_LEVEL = frozenset({"cc"})


def _flag_prefix(name: str) -> str:
    """按顶层前缀决定 CLI flag 前缀:``cc.*`` 用单横线,其余用 ``--``。"""
    top_level, _, _ = name.partition(".")
    return "-" if top_level in SINGLE_DASH_TOP_LEVEL else "--"


def is_flag_token(token: str) -> bool:
    """判断一个 argv token 是否为 flag:``--`` 长参数,或含点号的单横线嵌套配置(如 ``-cc.xxx``)。"""
    if token.startswith("--"):
        return True
    if token.startswith("-") and "." in token:
        return True
    return False


def kebab(name: str) -> str:
    top_level, dot, nested_path = name.partition(".")
    return _flag_prefix(name) + top_level.replace("_", "-") + dot + nested_path


def scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return str(value)


def normalize_value(value: str) -> str:
    """Ignore shell/YAML serialization differences for JSON-valued arguments."""
    if value.lower() in {"true", "false"}:
        return value.lower()
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value
    if isinstance(parsed, (dict, list)):
        return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
    return value


def add_argument(result: dict[str, str], flag: str, value: Any = "true") -> None:
    if not flag.startswith("-"):
        raise DryRunMismatch(f"invalid flag {flag!r}")
    result[flag] = scalar(value)


def render_command(arguments: dict[str, str]) -> str:
    """Render parsed arguments as a copyable shell command."""
    parts: list[str] = []
    for flag, value in arguments.items():
        if "." in flag:
            parts.append(f"{flag}={shlex.quote(value)}")
            continue
        parts.append(flag)
        if value != "true":
            parts.append(shlex.quote(value))
    return " ".join(parts)


def parse_tokens(tokens: list[str], engine: str) -> dict[str, str]:
    """Parse one engine command into flag/value pairs."""
    tokens = [str(token) for token in tokens]
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
        if not is_flag_token(token):
            index += 1
            continue
        if "=" in token:
            flag, value = token.split("=", 1)
            add_argument(result, flag, value)
            index += 1
            continue
        if index + 1 < len(positional) and not is_flag_token(positional[index + 1]):
            add_argument(result, token, positional[index + 1])
            index += 2
        else:
            add_argument(result, token)
            index += 1
    return result


def canonicalize_sglang_arguments(arguments: dict[str, str]) -> dict[str, str]:
    """Normalize legacy SGLang parallelism aliases for semantic comparison."""
    normalized = dict(arguments)
    for legacy, canonical in (("--tp", "--tp-size"), ("--dp", "--dp-size"), ("--ep", "--ep-size")):
        if legacy in normalized and canonical not in normalized:
            normalized[canonical] = normalized.pop(legacy)
    return normalized


def canonicalize_vllm_arguments(arguments: dict[str, str]) -> dict[str, str]:
    """Treat vLLM underscore and kebab-case spellings as equivalent; keep ``cc.*`` single-dash."""
    normalized: dict[str, str] = {}
    for flag, value in arguments.items():
        prefix = "--" if flag.startswith("--") else "-"
        top_level, dot, nested_path = flag[len(prefix):].partition(".")
        normalized[prefix + top_level.replace("_", "-") + dot + nested_path] = value
    return normalized


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
            if key in IGNORED_ENV_VARS:
                continue
            result[key] = value
    return result


def _extract_source_paths(lines: list[str], source_label: str) -> list[str]:
    """从命令行中提取 ``source <path>`` 路径，并保留出现顺序。"""
    sources: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line.startswith("source"):
            continue
        try:
            tokens = shlex.split(line, comments=True, posix=True)
        except ValueError as exc:
            raise DryRunMismatch(f"invalid {source_label} source command: {line!r}") from exc
        if not tokens or tokens[0] != "source":
            continue
        if len(tokens) != 2 or not tokens[1].startswith("/"):
            raise DryRunMismatch(
                f"{source_label} source command must be 'source <absolute-path>': {line!r}"
            )
        sources.append(tokens[1])
    return sources


def command_source_commands(text: str) -> list[str]:
    """提取启动脚本中的 ``source <path>`` 命令，并保留出现顺序。"""
    return _extract_source_paths(text.splitlines(), "command")


def yaml_environment(config: dict[str, Any]) -> dict[str, str]:
    """Return YAML ``env`` values in the same scalar form as shell exports."""
    env = config.get("env", {})
    if env is None:
        return {}
    if not isinstance(env, dict):
        raise DryRunMismatch("engine_config.env must be a mapping")
    return {str(key): scalar(value) for key, value in env.items()}


def yaml_source_commands(system_setup: Any) -> list[str]:
    """提取 YAML ``system_setup.commands`` 中的 source 路径，并保留出现顺序。"""
    if system_setup is None:
        return []
    if not isinstance(system_setup, dict):
        raise DryRunMismatch("system_setup must be a mapping")
    commands = system_setup.get("commands", [])
    if commands is None:
        return []
    if not isinstance(commands, list):
        raise DryRunMismatch("system_setup.commands must be a list")

    if not all(isinstance(command, str) for command in commands):
        raise DryRunMismatch("system_setup.commands must contain only strings")
    return _extract_source_paths(commands, "YAML")


def compare_environment(
    expected: dict[str, str],
    actual: dict[str, str],
    label: str,
    ignored_variables: frozenset[str] = frozenset(),
) -> list[str]:
    """Compare YAML environment variables with explicit command exports."""
    expected = {key: value for key, value in expected.items() if key not in ignored_variables}
    actual = {key: value for key, value in actual.items() if key not in ignored_variables}
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


def compare_source_commands(expected: list[str], actual: list[str], label: str) -> list[str]:
    """比较 YAML 与原始启动脚本中的 source 命令，顺序也属于启动契约。"""
    details = [f"{label} source commands: {'OK' if expected == actual else '异常'}"]
    for index, (yaml_path, command_path) in enumerate(zip(expected, actual)):
        if yaml_path == command_path:
            details.append(f"  OK       source[{index}]: {yaml_path!r}")
        else:
            details.append(
                f"  不一致   source[{index}]: YAML={yaml_path!r}, command={command_path!r}"
            )
    for index, yaml_path in enumerate(expected[len(actual):], start=len(actual)):
        details.append(f"  缺失     source[{index}]: YAML={yaml_path!r}")
    for index, command_path in enumerate(actual[len(expected):], start=len(expected)):
        details.append(f"  多余     source[{index}]: command={command_path!r}")
    if expected != actual:
        raise DryRunMismatch("\n".join(details))
    return details


def command_tokens(text: str) -> list[str]:
    try:
        tokens = shlex.split(text, comments=True, posix=True)
    except ValueError as exc:
        raise DryRunMismatch(f"invalid shell command: {exc}") from exc
    tokens = [token.strip() for token in tokens if token.strip()]
    if "vllm" in tokens and "serve" in tokens:
        return tokens[tokens.index("vllm") :]
    if "sglang" in tokens:
        return tokens[tokens.index("sglang") :]
    for index, token in enumerate(tokens):
        if token == "sglang.launch_server":
            return ["sglang", *tokens[index + 1 :]]
    raise DryRunMismatch("no supported engine launch command found")


def iter_engine_configs(strategy: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], Any]]:
    configs: list[tuple[dict[str, Any], dict[str, Any], Any]] = []
    strategy_env = strategy.get("env", {})
    strategy_setup = strategy.get("system_setup")
    if isinstance(strategy.get("engine_config"), dict):
        configs.append((strategy["engine_config"], strategy_env, strategy_setup))
    for role in ("head", "worker"):
        node = strategy.get(role)
        if isinstance(node, dict) and isinstance(node.get("engine_config"), dict):
            configs.append(
                (node["engine_config"], node.get("env", strategy_env), node.get("system_setup", strategy_setup))
            )
    for node in strategy.get("nodes", []) or []:
        if isinstance(node, dict) and isinstance(node.get("engine_config"), dict):
            configs.append(
                (node["engine_config"], node.get("env", strategy_env), node.get("system_setup", strategy_setup))
            )
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
    feature_names = [
        *DEFAULT_ENABLED_FEATURES,
        *(name for name in features if name not in DEFAULT_ENABLED_FEATURES),
    ]
    for feature_name in feature_names:
        feature = features.get(feature_name)
        if not isinstance(feature, dict):
            continue
        args = feature.get("args", [])
        if not isinstance(args, list):
            continue
        feature_args.update(parse_tokens(["sglang", *args], "sglang"))
    result: list[dict[str, Any]] = []
    for config, strategy_env, system_setup in iter_engine_configs(strategy):
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
        result.append(
            {
                "arguments": values,
                "env": yaml_environment({"env": environment}),
                "source_commands": yaml_source_commands(system_setup),
            }
        )
    return result


def validate_chat_template_source(
    expected: dict[str, str], actual: dict[str, str], label: str
) -> None:
    """Require a YAML chat template to be explicitly present in the user command."""
    yaml_template = expected.get(CHAT_TEMPLATE_FLAG)
    if yaml_template is None:
        return
    command_template = actual.get(CHAT_TEMPLATE_FLAG)
    if command_template is None:
        raise DryRunMismatch(
            f"{label}: YAML contains {CHAT_TEMPLATE_FLAG}={yaml_template!r}, but the "
            "user-provided launch command does not. A chat template must originate "
            "from the user command, not a reference or fallback configuration."
        )
    if normalize_value(yaml_template) != normalize_value(command_template):
        raise DryRunMismatch(
            f"{label}: YAML {CHAT_TEMPLATE_FLAG}={yaml_template!r} does not match "
            f"the user-provided launch command value {command_template!r}."
        )


def compare(
    expected: dict[str, str],
    actual: dict[str, str],
    label: str,
    engine: str,
    ignored_flags: frozenset[str] = frozenset(),
) -> list[str]:
    # vLLM YAMLs may use a distributable HF/ModelScope ID instead of a
    # machine-local absolute model path and omit served_model_name as a
    # deployment-local API alias. Keep strict comparison for all other
    # explicitly represented parameters.
    comparable_expected = dict(expected)
    comparable_actual = dict(actual)
    if engine == "sglang":
        comparable_expected = canonicalize_sglang_arguments(comparable_expected)
        comparable_actual = canonicalize_sglang_arguments(comparable_actual)
    elif engine in {"vllm", "vllm-ascend"}:
        comparable_expected = canonicalize_vllm_arguments(comparable_expected)
        comparable_actual = canonicalize_vllm_arguments(comparable_actual)
    if comparable_actual.get("--model", "").startswith("/"):
        comparable_expected.pop("--model", None)
        comparable_actual.pop("--model", None)
    if (
        engine == "sglang"
        and comparable_actual.get("--model-path", "").startswith("/")
        and "--model-path" in comparable_expected
    ):
        comparable_expected.pop("--model", None)
        comparable_expected.pop("--model-path", None)
        comparable_actual.pop("--model-path", None)
    if engine == "vllm":
        comparable_expected.pop("--served-model-name", None)
        comparable_actual.pop("--served-model-name", None)
    for flag in ignored_flags:
        comparable_expected.pop(flag, None)
        comparable_actual.pop(flag, None)

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
    source_commands = [command_source_commands(text) for text in command_texts]
    if len(configs) != len(commands):
        raise DryRunMismatch(
            f"YAML has {len(configs)} engine configs but commands provide {len(commands)}"
        )
    auto_env_ignored = (
        RTX_PRO_5000_AUTO_ENV_VARS
        if any(part.startswith("rtx_pro_5000") for part in yaml_path.parts)
        else frozenset()
    )
    report: list[str] = []
    for index, (expected, actual, environment, sources) in enumerate(
        zip(configs, commands, environments, source_commands)
    ):
        label = f"node[{index}]"
        expected_arguments = expected["arguments"]
        expected_environment = expected["env"]
        expected_source_commands = expected["source_commands"]
        report.extend(
            [
                f"[{label}] YAML 重建命令:",
                f"  {render_command(expected_arguments)}",
                f"[{label}] 原始启动命令:",
                f"  {render_command(actual)}",
            ]
        )
        try:
            ignored_flags = (
                frozenset({"--host"})
                if engine == "sglang" or scenario == "standalone"
                else frozenset()
            )
            validate_chat_template_source(expected_arguments, actual, label)
            report.extend(compare(expected_arguments, actual, label, engine, ignored_flags))
            report.extend(
                compare_environment(
                    expected_environment,
                    environment,
                    label,
                    auto_env_ignored,
                )
            )
            report.extend(compare_source_commands(expected_source_commands, sources, label))
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
