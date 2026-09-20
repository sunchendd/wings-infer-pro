"""GLM-5.3 四套 exact PD recipe 的最小回归测试。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from wings_ctl.core.models import (
    ClusterPlacement,
    ExplicitPdTopology,
    ParallelShape,
    PdRole,
    PdRuntimeInput,
    PipelineRequest,
    Target,
    UserInput,
)
from wings_ctl.core.topology import Topology
from wings_ctl.pd.recipe import select_pd_recipe_pair
from wings_ctl.pipeline import resolve_pipeline


_VARIANTS = {
    "GLM-5.3-w8a8c8-128k-4node": (4, 2, 8),
    "GLM-5.3-w8a8c8-128k-6node": (6, 2, 8),
    "GLM-5.3-w8a8c8-1m-4node": (4, 2, 4),
    "GLM-5.3-w8a8c8-1m-6node": (6, 2, 4),
}


@dataclass(frozen=True)
class ProcessPlanCase:
    """一个 GLM-5.3 示例 Pod 的预期进程规划。"""

    variant: str
    pod: str
    tp_size: int
    prefill_dp: int
    decode_dp: int
    decode_tp: int
    dp_rpc_port: int
    kv_port: int


_PROCESS_PLAN_CASES = (
    ProcessPlanCase("GLM-5.3-w8a8c8-128k-4node", "p1", 16, 2, 8, 4, 7060, 30000),
    ProcessPlanCase("GLM-5.3-w8a8c8-128k-4node", "d1", 4, 2, 8, 4, 12321, 30200),
    ProcessPlanCase("GLM-5.3-w8a8c8-128k-6node", "p2", 16, 2, 8, 4, 12321, 30000),
    ProcessPlanCase("GLM-5.3-w8a8c8-128k-6node", "d1", 4, 2, 8, 4, 12321, 30200),
    ProcessPlanCase("GLM-5.3-w8a8c8-1m-4node", "p1", 16, 2, 4, 8, 16591, 30000),
    ProcessPlanCase("GLM-5.3-w8a8c8-1m-4node", "d1", 8, 2, 4, 8, 16600, 30200),
    ProcessPlanCase("GLM-5.3-w8a8c8-1m-6node", "p2", 16, 2, 4, 8, 16591, 30000),
    ProcessPlanCase("GLM-5.3-w8a8c8-1m-6node", "d1", 8, 2, 4, 8, 16600, 30200),
)


def _read_example_env(path: Path) -> dict[str, str]:
    """读取仓库内不含 shell 展开的静态示例环境文件。"""
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )


def _argv_value(argv: list[str], option: str) -> str:
    """返回结构化 engine argv 中指定选项的值。"""
    return argv[argv.index(option) + 1]


@pytest.mark.parametrize(
    ("variant", "node_count", "prefill_dp", "decode_dp"),
    [(variant, *values) for variant, values in _VARIANTS.items()],
)
def test_glm53_exact_recipe_and_example(
    config_root_real: Path,
    variant: str,
    node_count: int,
    prefill_dp: int,
    decode_dp: int,
) -> None:
    """四套资产必须无 PP、匹配对应示例，并保留 MultiConnector runtime 策略。"""
    recipe_path = config_root_real / "engines/vllm-ascend/v0.26.0rc/ascend-a3/models/GLM-5.3" / f"{variant}.yaml"
    recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    strategy = recipe["scenarios"]["pd_disaggregation"]["strategies"]["pd_cluster"]
    nodes = strategy["nodes"]
    pair = select_pd_recipe_pair(recipe, "explicit_allocation")

    assert recipe["model"]["variant_name"] == variant
    assert [(node["role"], node["index"]) for node in nodes] == [
        ("prefill", 0),
        ("prefill", 1),
        ("decode", 0),
        ("decode", 1),
    ]
    assert all(role.runtime.data_parallel_external_lb is False for role in pair.values())
    assert pair[PdRole.PREFILL].runtime.connector_profile.engine_id_policy == "from_pd_index"
    assert pair[PdRole.DECODE].runtime.connector_profile.engine_id_policy == "from_pd_index"
    assert pair[PdRole.PREFILL].runtime.prefill_shape.dp_size == prefill_dp
    assert pair[PdRole.DECODE].runtime.decode_shape.dp_size == decode_dp
    assert all("pp_size" not in str(node) for node in nodes)
    assert {node["engine_config"]["data_parallel_size"] for node in nodes if node["role"] == "prefill"} == {prefill_dp}
    assert {node["engine_config"]["data_parallel_size"] for node in nodes if node["role"] == "decode"} == {decode_dp}
    assert all(node["engine_config"]["kv_transfer_config"]["kv_connector"] == "MultiConnector" for node in nodes)

    example_name = variant.lower().replace("glm-5.3", "glm5.3", 1)
    example = config_root_real.parents[1] / "ai_perf" / "example" / "ascend-a3" / example_name
    assert example.is_dir()
    assert f"--model-name {variant}" in (example / "control-entrypoint.sh").read_text(encoding="utf-8")
    assert len(list((example / "env").glob("[pd][0-9].env"))) == node_count


@pytest.mark.parametrize("case", _PROCESS_PLAN_CASES)
def test_glm53_example_resolves_expected_process_argv(
    config_root_real: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: ProcessPlanCase,
) -> None:
    """真实 4/6 节点 P/D 示例必须生成正确的进程、DP、端口和 connector argv。"""
    example_name = case.variant.lower().replace("glm-5.3", "glm5.3", 1)
    example = config_root_real.parents[1] / "ai_perf" / "example" / "ascend-a3" / example_name
    common = _read_example_env(example / "env" / "common.env")
    current = _read_example_env(example / "env" / f"{case.pod}.env")
    role = PdRole(current["PD_ROLE"])
    placement = ClusterPlacement(
        master_ip=current["MASTER_IP"],
        rank_ip=current["RANK_IP"],
        node_ips=current["NODE_IPS"].split(","),
    )
    pd_input = PdRuntimeInput(
        role=role,
        explicit_topology=ExplicitPdTopology(
            pd_index=int(current["PD_INDEX"]),
            prefill=ParallelShape(
                dp_size=int(common["PD_PREFILL_DP_SIZE"]),
                tp_size=int(common["PD_PREFILL_TP_SIZE"]),
            ),
            decode=ParallelShape(
                dp_size=int(common["PD_DECODE_DP_SIZE"]),
                tp_size=int(common["PD_DECODE_TP_SIZE"]),
            ),
            dp_size_local=int(current["DP_SIZE_LOCAL"]),
        ),
        placement=placement,
    )
    monkeypatch.setenv("ENGINE_VERSION", common["ENGINE_VERSION"])

    resolved = resolve_pipeline(
        PipelineRequest(
            target=Target(
                case.variant,
                Topology.PD_PREFILL if role is PdRole.PREFILL else Topology.PD_DECODE,
                "vllm-ascend",
            ),
            hardware_info_path=example / "config" / "hardware_info.json",
            config_root=config_root_real,
            device_count=16,
            placement=placement,
            pd_input=pd_input,
        )
    )

    assert resolved.resolution_notes["matched_name_pattern"] == f"variant_name={case.variant}"
    assert Path(resolved.resolution_notes["matched_model_yaml"]).name == f"{case.variant}.yaml"
    assert resolved.process_plan is not None
    plan = resolved.process_plan
    expected_local_dp = int(current["DP_SIZE_LOCAL"])
    member_index = placement.node_ips.index(placement.rank_ip)
    expected_ranks = list(range(member_index * expected_local_dp, (member_index + 1) * expected_local_dp))
    assert plan.layout == "per_local_dp_rank"
    assert [process.dp_rank for process in plan.processes] == expected_ranks
    assert plan.endpoints == [f"{placement.rank_ip}:{17000 + index}" for index in range(expected_local_dp)]

    expected_kv_role = "kv_producer" if role is PdRole.PREFILL else "kv_consumer"
    for local_index, process in enumerate(plan.processes):
        assert process.visible_devices == tuple(
            range(local_index * case.tp_size, (local_index + 1) * case.tp_size)
        )
        assert _argv_value(process.argv, "--port") == str(17000 + local_index)
        assert _argv_value(process.argv, "--tensor-parallel-size") == str(case.tp_size)
        assert _argv_value(process.argv, "--data-parallel-size") == str(
            case.prefill_dp if role is PdRole.PREFILL else case.decode_dp
        )
        assert _argv_value(process.argv, "--data-parallel-rank") == str(expected_ranks[local_index])
        assert _argv_value(process.argv, "--data-parallel-size-local") == "1"
        assert _argv_value(process.argv, "--data-parallel-address") == placement.master_ip
        assert _argv_value(process.argv, "--data-parallel-rpc-port") == str(case.dp_rpc_port)

        transfer = json.loads(_argv_value(process.argv, "--kv-transfer-config"))
        assert transfer["kv_connector"] == "MultiConnector"
        assert transfer["kv_role"] == expected_kv_role
        assert transfer["engine_id"] == current["PD_INDEX"]
        connectors = transfer["kv_connector_extra_config"]["connectors"]
        mooncake, ascend_store = connectors
        assert mooncake["kv_connector"] == "MooncakeConnectorV1"
        assert mooncake["kv_role"] == expected_kv_role
        assert mooncake["kv_port"] == case.kv_port
        assert mooncake["kv_connector_extra_config"]["prefill"] == {"dp_size": case.prefill_dp, "tp_size": 16}
        assert mooncake["kv_connector_extra_config"]["decode"] == {
            "dp_size": case.decode_dp,
            "tp_size": case.decode_tp,
        }
        assert ascend_store["kv_connector"] == "AscendStoreConnector"
        assert ascend_store["kv_role"] == expected_kv_role
        assert ascend_store["kv_connector_extra_config"]["lookup_rpc_port"] == expected_ranks[local_index]


def _resolve_example_pod(
    config_root_real: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: ProcessPlanCase,
    *,
    engine_port: int | None = None,
) -> object:
    """按示例 Pod 的 env 构造解析请求,返回 ResolvedConfig(engine_port 为可选覆盖)。"""
    example_name = case.variant.lower().replace("glm-5.3", "glm5.3", 1)
    example = config_root_real.parents[1] / "ai_perf" / "example" / "ascend-a3" / example_name
    common = _read_example_env(example / "env" / "common.env")
    current = _read_example_env(example / "env" / f"{case.pod}.env")
    role = PdRole(current["PD_ROLE"])
    placement = ClusterPlacement(
        master_ip=current["MASTER_IP"],
        rank_ip=current["RANK_IP"],
        node_ips=current["NODE_IPS"].split(","),
    )
    pd_input = PdRuntimeInput(
        role=role,
        explicit_topology=ExplicitPdTopology(
            pd_index=int(current["PD_INDEX"]),
            prefill=ParallelShape(
                dp_size=int(common["PD_PREFILL_DP_SIZE"]),
                tp_size=int(common["PD_PREFILL_TP_SIZE"]),
            ),
            decode=ParallelShape(
                dp_size=int(common["PD_DECODE_DP_SIZE"]),
                tp_size=int(common["PD_DECODE_TP_SIZE"]),
            ),
            dp_size_local=int(current["DP_SIZE_LOCAL"]),
        ),
        placement=placement,
    )
    monkeypatch.setenv("ENGINE_VERSION", common["ENGINE_VERSION"])
    return resolve_pipeline(
        PipelineRequest(
            target=Target(
                case.variant,
                Topology.PD_PREFILL if role is PdRole.PREFILL else Topology.PD_DECODE,
                "vllm-ascend",
            ),
            hardware_info_path=example / "config" / "hardware_info.json",
            config_root=config_root_real,
            device_count=16,
            placement=placement,
            pd_input=pd_input,
            user_input=UserInput(engine_port=engine_port),
        )
    )


@pytest.mark.parametrize(
    ("case", "rank_ip", "expected_local_dp"),
    [
        # prefill Pod(local_dp=1,单进程)与 decode Pod(local_dp=2,多进程)各取一个。
        (ProcessPlanCase("GLM-5.3-w8a8c8-1m-6node", "p2", 16, 2, 4, 8, 16591, 30000), "192.0.2.39", 1),
        (ProcessPlanCase("GLM-5.3-w8a8c8-1m-6node", "d1", 8, 2, 4, 8, 16600, 30200), "192.0.2.42", 2),
    ],
)
def test_glm53_engine_port_cli_override_rewrites_endpoint_profile(
    config_root_real: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: ProcessPlanCase,
    rank_ip: str,
    expected_local_dp: int,
) -> None:
    """--engine-port(UserInput.engine_port)覆盖 recipe 端口基座,进程仍为 base+index。"""
    monkeypatch.delenv("ENGINE_PORT", raising=False)
    resolved = _resolve_example_pod(config_root_real, monkeypatch, case, engine_port=17500)

    plan = resolved.process_plan
    assert plan.endpoints == [f"{rank_ip}:{17500 + index}" for index in range(expected_local_dp)]
    for local_index, process in enumerate(plan.processes):
        assert _argv_value(process.argv, "--port") == str(17500 + local_index)
    assert resolved.resolution_notes["pd.engine_port_base"] == "17500"
    assert resolved.resolution_notes["pd.engine_port_base_source"] == "--engine-port"


def test_glm53_engine_port_env_override_writes_env_source(
    config_root_real: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未传 --engine-port 时,ambient ENGINE_PORT 作为端口基座覆盖,来源写入 notes。"""
    monkeypatch.setenv("ENGINE_PORT", "17600")
    case = ProcessPlanCase("GLM-5.3-w8a8c8-1m-6node", "d1", 8, 2, 4, 8, 16600, 30200)

    resolved = _resolve_example_pod(config_root_real, monkeypatch, case)

    assert resolved.process_plan.endpoints == ["192.0.2.42:17600", "192.0.2.42:17601"]
    assert resolved.resolution_notes["pd.engine_port_base"] == "17600"
    assert resolved.resolution_notes["pd.engine_port_base_source"] == "ENGINE_PORT env"


def test_glm53_engine_port_override_conflict_with_rpc_rejected(
    config_root_real: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """覆盖端口与 DP RPC 端口区间重叠时,解析以可定位错误失败。

    DP RPC listener 只在 rank-zero Pod(d0)注册,冲突用例使用 d0。
    """
    monkeypatch.delenv("ENGINE_PORT", raising=False)
    case = ProcessPlanCase("GLM-5.3-w8a8c8-1m-6node", "d0", 8, 2, 4, 8, 16600, 30200)

    with pytest.raises(ValueError, match="PD listener conflict"):
        _ = _resolve_example_pod(config_root_real, monkeypatch, case, engine_port=16600)
