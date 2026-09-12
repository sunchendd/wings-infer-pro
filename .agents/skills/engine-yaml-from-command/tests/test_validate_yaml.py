from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_yaml.py"
spec = importlib.util.spec_from_file_location("validate_yaml", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def scenario_data(scenario: str, rpc_port: object) -> dict:
    if scenario == "multi_node":
        strategy = {
            "default_strategy": True,
            "head": {"engine_config": {"model": "demo/model", "data_parallel_rpc_port": rpc_port}},
            "worker": {"engine_config": {"model": "demo/model", "data_parallel_rpc_port": rpc_port}},
        }
    else:
        strategy = {
            "default_strategy": True,
            "nodes": [
                {
                    "role": "prefill",
                    "index": 0,
                    "engine_config": {"model": "demo/model", "data_parallel_rpc_port": rpc_port},
                },
                {
                    "role": "decode",
                    "index": 0,
                    "engine_config": {"model": "demo/model", "data_parallel_rpc_port": rpc_port},
                },
            ],
        }
    return {
        "scenarios": {
            scenario: {
                "match": {"distributed": True, "pd_role": None},
                "strategies": {"default": strategy},
            }
        }
    }


@pytest.mark.parametrize("scenario", ["multi_node", "pd_disaggregation"])
@pytest.mark.parametrize("rpc_port", ["$6", "12321"])
def test_rejects_non_numeric_data_parallel_rpc_port(scenario: str, rpc_port: str) -> None:
    with pytest.raises(module.ValidationError, match="data_parallel_rpc_port must be a YAML integer"):
        module.validate_scenarios(scenario_data(scenario, rpc_port), "vllm", scenario)


@pytest.mark.parametrize("scenario", ["multi_node", "pd_disaggregation"])
def test_accepts_numeric_data_parallel_rpc_port(scenario: str) -> None:
    module.validate_scenarios(scenario_data(scenario, 12321), "vllm", scenario)


@pytest.mark.parametrize("field", ["engine_id", "kv_port"])
@pytest.mark.parametrize("value", ["0", "2", "$1"])
def test_rejects_non_numeric_kv_transfer_field(field: str, value: str) -> None:
    data = {
        "scenarios": {
            "pd_disaggregation": {
                "match": {"distributed": True, "pd_role": None},
                "strategies": {
                    "default": {
                        "default_strategy": True,
                        "nodes": [
                            {
                                "role": "prefill",
                                "index": 0,
                                "engine_config": {
                                    "model": "demo/model",
                                    "kv_transfer_config": {field: value},
                                },
                            },
                            {
                                "role": "decode",
                                "index": 0,
                                "engine_config": {
                                    "model": "demo/model",
                                    "kv_transfer_config": {field: value},
                                },
                            },
                        ],
                    }
                },
            }
        }
    }
    with pytest.raises(module.ValidationError, match=f"kv_transfer_config\\.{field} must be a YAML integer"):
        module.validate_scenarios(data, "vllm", "pd_disaggregation")


@pytest.mark.parametrize("field", ["engine_id", "kv_port"])
def test_accepts_numeric_kv_transfer_field(field: str) -> None:
    data = {
        "scenarios": {
            "pd_disaggregation": {
                "match": {"distributed": True, "pd_role": None},
                "strategies": {
                    "default": {
                        "default_strategy": True,
                        "nodes": [
                            {
                                "role": "prefill",
                                "index": 0,
                                "engine_config": {
                                    "model": "demo/model",
                                    "kv_transfer_config": {field: 0},
                                },
                            },
                            {
                                "role": "decode",
                                "index": 0,
                                "engine_config": {
                                    "model": "demo/model",
                                    "kv_transfer_config": {field: 2},
                                },
                            },
                        ],
                    }
                },
            }
        }
    }
    module.validate_scenarios(data, "vllm", "pd_disaggregation")


def reasoning_data() -> dict:
    return {
        "model": {"variant_name": "MiniMax-M2.5-nvfp4"},
        "features": {
            "reasoning": {
                "args": ["--reasoning-parser", "minimax_m2"],
            }
        },
    }


def test_reasoning_requires_registry_when_yaml_enables_it() -> None:
    with pytest.raises(module.ValidationError, match="--reasoning-registry is required"):
        module.validate_reasoning_registry_presence(reasoning_data(), None)


def test_reasoning_accepts_existing_registry_entry_without_parser_comparison(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "reason_parser.yaml"
    registry.write_text(
        """
architectures:
  - name: MiniMax
    models:
      MiniMax-M2.5-NVFP4:
        vllm: different_parser
        vllm_ascend: another_parser
""",
        encoding="utf-8",
    )
    module.validate_reasoning_registry_presence(reasoning_data(), registry)


def test_reasoning_requires_missing_variant_to_be_registered(tmp_path: Path) -> None:
    registry = tmp_path / "reason_parser.yaml"
    registry.write_text(
        """
architectures:
  - name: MiniMax
    models: {}
""",
        encoding="utf-8",
    )
    with pytest.raises(module.ValidationError, match="Add the missing model entry"):
        module.validate_reasoning_registry_presence(reasoning_data(), registry)


def test_reasoning_rejects_non_mapping_registry_entry(tmp_path: Path) -> None:
    registry = tmp_path / "reason_parser.yaml"
    registry.write_text(
        """
architectures:
  - name: MiniMax
    models:
      MiniMax-M2.5-NVFP4: null
""",
        encoding="utf-8",
    )
    with pytest.raises(
        module.ValidationError,
        match="MiniMax.models.MiniMax-M2.5-NVFP4 must be a mapping",
    ):
        module.validate_reasoning_registry_presence(reasoning_data(), registry)


def test_reasoning_requires_parser_in_yaml_args() -> None:
    with pytest.raises(
        module.ValidationError,
        match="must contain --reasoning-parser",
    ):
        module.validate_reasoning_registry_presence(
            {
                "model": {"variant_name": "MiniMax-M2.5-nvfp4"},
                "features": {
                    "reasoning": {
                        "args": ["--enable-auto-think-choice"],
                    }
                }
            },
            None,
        )
