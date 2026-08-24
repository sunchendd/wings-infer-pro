from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "normalize_input.py"
spec = importlib.util.spec_from_file_location("normalize_input", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_non_numeric_data_parallel_rpc_port_warns_for_multi_node() -> None:
    warnings = module.data_parallel_rpc_port_warnings(
        "multi_node",
        [{"path": "/tmp/head.sh", "text": "vllm serve model --data-parallel-rpc-port $6"}],
    )

    assert len(warnings) == 1
    assert "12321" in warnings[0]
    assert "confirm" in warnings[0]


def test_numeric_data_parallel_rpc_port_does_not_warn() -> None:
    warnings = module.data_parallel_rpc_port_warnings(
        "pd_disaggregation",
        [{"path": "/tmp/decode.sh", "text": "vllm serve model --data_parallel_rpc_port=16600"}],
    )

    assert warnings == []


def test_standard_engine_version_needs_no_warning() -> None:
    assert module.validate_engine_version("v0.5.14", False) is None


@pytest.mark.parametrize("engine_version", ["kimi-k3", "vendor-0day-20260824"])
def test_special_engine_version_requires_explicit_confirmation(engine_version: str) -> None:
    with pytest.raises(SystemExit) as error:
        module.validate_engine_version(engine_version, False)

    assert error.value.code == 2


@pytest.mark.parametrize("engine_version", ["kimi-k3", "vendor-0day-20260824"])
def test_confirmed_special_engine_version_is_allowed_with_warning(engine_version: str) -> None:
    warning = module.validate_engine_version(engine_version, True)

    assert warning is not None
    assert "user-confirmed special/custom" in warning


def test_empty_special_engine_version_is_rejected() -> None:
    with pytest.raises(SystemExit) as error:
        module.validate_engine_version("   ", True)

    assert error.value.code == 2


def test_missing_variant_defaults_to_model_name() -> None:
    assert module.resolve_variant("DeepSeek-V3.1", None) == "DeepSeek-V3.1"


def test_explicit_variant_is_normalized() -> None:
    assert module.resolve_variant("DeepSeek-V3.1", " BF16 ") == "bf16"


def test_empty_explicit_variant_is_rejected() -> None:
    with pytest.raises(SystemExit) as error:
        module.resolve_variant("DeepSeek-V3.1", " ")

    assert error.value.code == 2
