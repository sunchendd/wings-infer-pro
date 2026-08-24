#!/usr/bin/env python3
"""校验并规范化从启动命令生成 YAML 所需的输入。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ENGINES = ("vllm", "vllm-ascend", "sglang")
SCENARIOS = ("standalone", "multi_node", "pd_disaggregation")
VERSION_RE = re.compile(r"^v?\d+\.\d+\.\d+(?:rc\d*)?$")
SUSPICIOUS_SHELL_RE = re.compile(r"\\[()]")
DATA_PARALLEL_RPC_PORT_RE = re.compile(
    r"--data[-_]parallel[-_]rpc[-_]port(?:=|\s+)([^\s\\]+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and normalize engine YAML generation input."
    )
    parser.add_argument("--engine", required=True)
    parser.add_argument("--engine-version", required=True)
    parser.add_argument(
        "--allow-special-engine-version",
        action="store_true",
        help=(
            "Allow a non-semver 0day/custom engine version only after the user "
            "explicitly confirms that version."
        ),
    )
    parser.add_argument("--hardware-profile", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-id")
    parser.add_argument(
        "--allow-local-model-path",
        action="store_true",
        help="Allow an unconfirmed local model path instead of a model_id.",
    )
    parser.add_argument(
        "--variant",
        help="Explicit model variant. Defaults to the model name when omitted.",
    )
    parser.add_argument(
        "--command-file",
        action="append",
        required=True,
        metavar="[ROLE=]PATH",
        help="Repeat for multiple roles, e.g. head=head.sh or prefill=p.sh.",
    )
    parser.add_argument("--gpu-count", type=int)
    parser.add_argument("--vram-gb", type=int)
    parser.add_argument(
        "--multi-node-capable", choices=("true", "false")
    )
    return parser.parse_args()


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def validate_engine_version(
    engine_version: str, allow_special_engine_version: bool
) -> str | None:
    """Validate a normal version or explicitly confirmed custom version string."""
    if not engine_version.strip():
        fail("engine version must not be empty")
    if VERSION_RE.fullmatch(engine_version):
        return None
    if allow_special_engine_version:
        return (
            f"engine version {engine_version!r} is a user-confirmed special/custom "
            "release; semver validation was explicitly bypassed"
        )
    fail(
        f"invalid engine version {engine_version!r}; expected a complete version "
        "such as v0.21.0rc or v0.5.14. For a user-confirmed special/custom release, "
        "pass --allow-special-engine-version"
    )


def load_profiles() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / "references" / "hardware-profiles.json"
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def parse_command_files(values: list[str], engine: str) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    for value in values:
        role: str | None = None
        raw_path = value
        if "=" in value:
            possible_role, possible_path = value.split("=", 1)
            if possible_role in {"head", "worker", "prefill", "decode"}:
                role, raw_path = possible_role, possible_path

        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            fail(f"command file does not exist: {path}")

        result = subprocess.run(
            ["bash", "-n", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            detail = result.stderr.strip() or "bash -n failed"
            fail(f"invalid shell in {path}: {detail}")

        text = path.read_text(encoding="utf-8")
        command_name = "vllm" if engine in {"vllm", "vllm-ascend"} else "sglang"
        if command_name == "vllm" and not re.search(r"\bvllm\s+serve\b", text):
            fail(f"command file does not contain a vllm serve command: {path}")
        if command_name == "sglang" and not re.search(r"\bsglang\b", text):
            fail(f"command file does not contain an sglang command: {path}")
        match = SUSPICIOUS_SHELL_RE.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            fail(
                f"suspicious escaped parenthesis in {path}:{line}; "
                "confirm the original variable expression"
            )

        commands.append({"role": role or "", "path": str(path), "text": text})
    return commands


def validate_roles(scenario: str, commands: list[dict[str, str]]) -> None:
    roles = {item["role"] for item in commands if item["role"]}
    combined = "\n".join(item["text"] for item in commands)

    if scenario == "standalone":
        if roles - {""}:
            fail("standalone command files must not use distributed role labels")
        return

    if scenario == "multi_node":
        if {"head", "worker"}.issubset(roles):
            return
        has_head = bool(re.search(r"--node[-_]rank(?:=|\s+)0\b", combined))
        has_worker = bool(
            re.search(r"--node[-_]rank(?:=|\s+)[1-9]\d*\b", combined)
            or re.search(r"(?:^|\s)--headless(?:\s|\\|$)", combined)
        )
        if not (has_head and has_worker):
            fail(
                "multi_node requires head and worker commands; label files as "
                "head=PATH and worker=PATH when roles cannot be inferred"
            )
        return

    if {"prefill", "decode"}.issubset(roles):
        return
    has_prefill = bool(
        re.search(r"kv_producer|disaggregation[-_]mode(?:=|\s+)prefill", combined)
    )
    has_decode = bool(
        re.search(r"kv_consumer|disaggregation[-_]mode(?:=|\s+)decode", combined)
    )
    if not (has_prefill and has_decode):
        fail(
            "pd_disaggregation requires prefill and decode commands; label files as "
            "prefill=PATH and decode=PATH when roles cannot be inferred"
        )


def resolve_hardware(args: argparse.Namespace, profiles: dict[str, Any]) -> dict[str, Any]:
    known = profiles.get(args.engine, {}).get(args.hardware_profile)
    inferred_multi_node = args.scenario != "standalone"
    explicit_values = (args.gpu_count, args.vram_gb)

    if args.multi_node_capable is not None:
        explicit_multi_node = args.multi_node_capable == "true"
        if explicit_multi_node != inferred_multi_node:
            fail(
                "--multi-node-capable conflicts with the deployment scenario: "
                f"{args.scenario} implies multi_node={str(inferred_multi_node).lower()}"
            )

    if known is not None:
        if any(value is not None for value in explicit_values):
            explicit = {
                "gpu_count": args.gpu_count,
                "vram_gb": args.vram_gb,
            }
            conflicts = [
                key
                for key, value in explicit.items()
                if value is not None and value != known[key]
            ]
            if conflicts:
                fail(
                    f"explicit hardware values conflict with {args.engine}/"
                    f"{args.hardware_profile}: {', '.join(conflicts)}"
                )
        return {
            "id": args.hardware_profile,
            "gpu_count": known["gpu_count"],
            "vram_gb": known["vram_gb"],
            "multi_node": inferred_multi_node,
        }

    if None in explicit_values:
        fail("unknown hardware profile; provide --gpu-count and --vram-gb")
    return {
        "id": args.hardware_profile,
        "gpu_count": args.gpu_count,
        "vram_gb": args.vram_gb,
        "multi_node": inferred_multi_node,
    }


def resolve_variant(model_name: str, variant: str | None) -> str:
    """Use the model name when no precision or quantization variant is confirmed."""
    if variant is None:
        return model_name
    normalized = variant.strip()
    if not normalized:
        fail("variant must not be empty when provided")
    return normalized.lower()


def data_parallel_rpc_port_warnings(
    scenario: str, commands: list[dict[str, str]]
) -> list[str]:
    """Warn when a distributed command leaves the data-parallel RPC port unresolved."""
    if scenario not in {"multi_node", "pd_disaggregation"}:
        return []

    warnings: list[str] = []
    for command in commands:
        for match in DATA_PARALLEL_RPC_PORT_RE.finditer(command["text"]):
            value = match.group(1).strip("'\"")
            if value.isdecimal():
                continue
            warnings.append(
                "data_parallel_rpc_port is not numeric in "
                f"{command['path']} ({value!r}); render YAML with 12321 and ask "
                "the user to confirm the actual port before claiming dry-run success"
            )
    return warnings


def main() -> int:
    args = parse_args()
    if args.engine not in ENGINES:
        fail(f"unknown engine {args.engine!r}; expected one of {', '.join(ENGINES)}")
    if args.scenario not in SCENARIOS:
        fail(
            f"unknown scenario {args.scenario!r}; expected one of "
            f"{', '.join(SCENARIOS)}"
        )
    version_warning = validate_engine_version(
        args.engine_version, args.allow_special_engine_version
    )

    commands = parse_command_files(args.command_file, args.engine)
    validate_roles(args.scenario, commands)
    hardware = resolve_hardware(args, load_profiles())

    warnings = data_parallel_rpc_port_warnings(args.scenario, commands)
    if version_warning:
        warnings.insert(0, version_warning)
    if not args.model_name.strip():
        fail("model_name must not be empty")
    variant = resolve_variant(args.model_name, args.variant)
    if not args.model_id and not args.allow_local_model_path:
        fail(
            "model_id is not confirmed; provide --model-id or explicitly pass "
            "--allow-local-model-path"
        )
    if not args.model_id:
        warnings.append("local model path explicitly allowed without a confirmed model_id")

    output = {
        "engine": args.engine,
        "engine_version": args.engine_version,
        "hardware_profile": hardware,
        "scenario": args.scenario,
        "model": {
            "name": args.model_name,
            "model_id": args.model_id,
            "variant": variant,
        },
        "command_files": [
            {"role": item["role"] or None, "path": item["path"]}
            for item in commands
        ],
        "warnings": warnings,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
