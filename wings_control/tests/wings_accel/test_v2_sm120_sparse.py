"""RTX PRO 5000 v2 SmartAccel sparse policy regressions."""

from pathlib import Path

import pytest

from wings_accel import func_smart_accel
from wings_accel.yaml_loader import LoadFlags, load_smart_accel_from_yaml


_ASSET = (
    Path(__file__).parents[2]
    / "config/v2/vllm/v0.31.0/rtx_pro_5000_72G/DeepSeek-V4-Flash/DeepSeek-V4-Flash.yaml"
)


@pytest.mark.parametrize("topology", ["standalone", "multi_node"])
@pytest.mark.parametrize(
    ("sparse_level", "index_topk_freq"),
    [("performance_first", 8), ("accuracy_first", 4)],
)
def test_deepseek_v4_flash_sparse_policy(topology, sparse_level, index_topk_freq):
    """两个支持拓扑必须使用统一的性能优先和精度优先档位。"""
    smart_input = load_smart_accel_from_yaml(
        str(_ASSET),
        LoadFlags(sparse=True, sparse_level=sparse_level, topology=topology),
    )

    output = func_smart_accel(smart_input)

    assert output.smart_kv_sparse_scheme == sparse_level
    assert output.engine_params.engine_config["hf_overrides"] == {
        "index_topk_freq": index_topk_freq,
    }
