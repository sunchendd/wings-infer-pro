from __future__ import annotations

import importlib.util
from pathlib import Path


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
