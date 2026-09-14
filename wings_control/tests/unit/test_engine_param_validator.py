"""EngineParamValidator(I1)单测 + 真配置集成(docs/50 §6)。

覆盖:清单解析(缺/空/全注释)、版本层路径定位、逐参渲染比对(unsupported 命中 /
全支持 / bool·None 不误判 / 复合参数顶层名 / sglang native 不误判为 canonical)、
warn-only 不改参,以及 run_pipeline 端到端把 param_validation 落进 audit + startup_log。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from wings_ctl.core.models import (
    EngineVersion,
    HardwareContext,
    PipelineRequest,
    ResolvedConfig,
    ResolvedNode,
    Target,
    TracedValue,
)
from wings_ctl.core.topology import Topology
from wings_ctl.engines.vllm_adapter import build_argv
from wings_ctl.pipeline import run_pipeline
from wings_ctl.validators.engine_param_validator import (
    _load_supported_params,
    _resolve_supported_params_path,
    collect_unsupported,
    validate_engine_params,
)


# ─── helpers ──────────────────────────────────────────────────────────────


def _tv(value, layer: str = "model_scenario", source_path: str = "engine_config.x") -> TracedValue:
    """构造一个最小 TracedValue(测试用)。"""
    return TracedValue(
        final_value=value,
        final_layer=layer,
        source_file="model.yaml",
        source_path=source_path,
        events=[],
    )


def _make_resolved(
    traces: dict,
    *,
    engine: str = "vllm",
    resolved_version: str = "",
    has_version_dir: bool = False,
) -> ResolvedConfig:
    """构造一个最小 standalone ResolvedConfig(仅填 validator 需要的字段)。"""
    return ResolvedConfig(
        topology=Topology.STANDALONE,
        hardware=HardwareContext(hardware_family="nvidia-x", device="nvidia"),
        engine=engine,
        engine_version=EngineVersion(
            requested=None,
            resolved=resolved_version,
            is_fallback=False,
            has_version_dir=has_version_dir,
        ),
        engine_config_traces=traces,
        env_traces={},
        source_files=["model.yaml"],
    )


def _make_resolved_multinode(
    node_traces: list[tuple[str, dict]],
    *,
    engine: str = "vllm-ascend",
    resolved_version: str = "v0.18.0",
    has_version_dir: bool = True,
) -> ResolvedConfig:
    """构造一个 multi_node ResolvedConfig(顶层 traces 空、nodes 承载 per-node)。"""
    rc = _make_resolved(
        {}, engine=engine, resolved_version=resolved_version, has_version_dir=has_version_dir
    )
    rc.nodes = [
        ResolvedNode(role=role, index=None, engine_config_traces=traces, env_traces={})
        for role, traces in node_traces
    ]
    return rc


def _write_supported(root: Path, engine: str, flags: list[str], version: str | None = None) -> Path:
    """在 tmp config 树写一份 supported_params.txt,返回其路径。"""
    engine_dir = root / "engines" / engine
    if version:
        engine_dir = engine_dir / version
    engine_dir.mkdir(parents=True, exist_ok=True)
    path = engine_dir / "supported_params.txt"
    path.write_text("# 头部注释\n\n" + "\n".join(flags) + "\n", encoding="utf-8")
    return path


# ─── 清单解析(决策②)────────────────────────────────────────────────────


def test_load_supported_params_strips_comments_and_blanks(tmp_path):
    """去掉 # 注释行与空行,只保留 --long-option。"""
    p = tmp_path / "supported_params.txt"
    p.write_text("# comment\n\n--max-model-len\n--host\n  --port  \n", encoding="utf-8")
    assert _load_supported_params(p) == {"--max-model-len", "--host", "--port"}


def test_load_supported_params_missing_returns_none(tmp_path):
    """文件不存在 → None(触发 warn-skip 兜底)。"""
    assert _load_supported_params(tmp_path / "nope.txt") is None


def test_load_supported_params_empty_or_all_comment_returns_none(tmp_path):
    """空文件 / 全注释 → None(视同无有效清单)。"""
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    assert _load_supported_params(empty) is None
    only_comment = tmp_path / "c.txt"
    only_comment.write_text("# just a header\n\n", encoding="utf-8")
    assert _load_supported_params(only_comment) is None


# ─── 版本层路径定位(决策②)──────────────────────────────────────────────


def test_resolve_path_no_version_layer(tmp_path):
    """无版本层引擎(vllm)→ engines/{engine}/supported_params.txt。"""
    ev = EngineVersion(requested=None, resolved="", is_fallback=False, has_version_dir=False)
    path = _resolve_supported_params_path(tmp_path, "vllm", ev)
    assert path == tmp_path / "engines" / "vllm" / "supported_params.txt"


def test_resolve_path_with_version_layer(tmp_path):
    """有版本层引擎(sglang)→ engines/{engine}/v{resolved}/supported_params.txt。"""
    ev = EngineVersion(requested=None, resolved="v0.5.14", is_fallback=False, has_version_dir=True)
    path = _resolve_supported_params_path(tmp_path, "sglang", ev)
    assert path == tmp_path / "engines" / "sglang" / "v0.5.14" / "supported_params.txt"


# ─── collect_unsupported(决策①,helper 吃一个 traces dict)───────────────


def test_collect_unsupported_hit():
    """不在清单的 native key → 收进 unsupported,带来源 trace。"""
    traces = {
        "model": _tv("m"),
        "max_model_len": _tv(262144, source_path="engine_config.max_model_len"),
        "not_a_real_flag": _tv(1, source_path="engine_config.not_a_real_flag"),
    }
    supported = {"--max-model-len"}
    out = collect_unsupported(traces, supported)
    assert len(out) == 1
    assert out[0]["param"] == "not_a_real_flag"
    assert out[0]["rendered_as"] == "--not-a-real-flag"
    assert out[0]["source_file"] == "model.yaml"
    assert out[0]["source_path"] == "engine_config.not_a_real_flag"


def test_collect_unsupported_all_supported():
    """全部在清单 → 空列表。"""
    traces = {"model": _tv("m"), "max_model_len": _tv(1), "host": _tv("0.0.0.0")}
    supported = {"--max-model-len", "--host"}
    assert not collect_unsupported(traces, supported)


def test_collect_unsupported_model_keys_skipped():
    """model / model_path 走命令头,不在此校验(即使不在清单也不误判)。"""
    traces = {"model": _tv("m"), "model_path": _tv("/p")}
    assert not collect_unsupported(traces, supported=set())


def test_collect_unsupported_bool_false_and_none_not_flagged():
    """bool=False / None 渲染即跳过(不传引擎)→ 不判 unsupported。"""
    traces = {
        "model": _tv("m"),
        "some_false": _tv(False),
        "some_none": _tv(None),
    }
    assert not collect_unsupported(traces, supported=set())


def test_collect_unsupported_bool_true_flagged_when_absent():
    """bool=True 渲成无值 flag;不在清单 → 判 unsupported。"""
    traces = {"model": _tv("m"), "async_scheduling": _tv(True)}
    out = collect_unsupported(traces, {"--max-model-len"})
    assert [item["rendered_as"] for item in out] == ["--async-scheduling"]


def test_collect_unsupported_complex_param_top_level_name():
    """复合参数(dict 值)只校验顶层 flag 名(--kv-transfer-config),在清单 → 不误判。"""
    traces = {"model": _tv("m"), "kv_transfer_config": _tv({"kv_connector": "x"})}
    assert not collect_unsupported(traces, {"--kv-transfer-config"})


def test_collect_unsupported_nested_config_uses_top_level_flag():
    """点号嵌套配置渲成 --kernel-config.field=False,但按清单中的顶层 --kernel-config 校验。"""
    traces = {
        "model": _tv("m"),
        "kernel_config.enable_flashinfer_autotune": _tv(False),
    }
    assert not collect_unsupported(traces, {"--kernel-config"})


def test_collect_unsupported_cc_single_dash_not_flagged():
    """vLLM ``cc.*``(pass 配置)渲成单横线 ``-cc.field=False``,不按 ``--`` 清单比对、不误报。

    ``cc.*`` 是引擎原生单横线参数,不在 ``--long-option`` 支持清单的比对范围。
    """
    traces = {
        "model": _tv("m"),
        "cc.pass_config.fuse_allreduce_rms": _tv(False),
    }
    assert not collect_unsupported(traces, {"--max-model-len"})


def test_collect_unsupported_sglang_native_not_confused_with_canonical():
    """sglang native context_length 命中 sglang 清单;不因 canonical max_model_len 误判(决策①)。"""
    traces = {"model": _tv("m"), "context_length": _tv(75000)}
    # sglang 清单存 native --context-length(非 canonical --max-model-len)
    assert not collect_unsupported(traces, {"--context-length"})
    # 若错在 canonical 层比对(清单只有 --max-model-len)则会误报,验证不会:
    out = collect_unsupported(traces, {"--max-model-len"})
    assert [item["rendered_as"] for item in out] == ["--context-length"]


def test_collect_unsupported_alias_benign_false_positive():
    """良性误报(取 A):yaml 用 tp 渲成 --tp,清单只列 --tp-size → warn 一条(不消误报)。"""
    traces = {"model": _tv("m"), "tp": _tv(8)}
    out = collect_unsupported(traces, {"--tp-size"})
    assert [item["rendered_as"] for item in out] == ["--tp"]


# ─── validate_engine_params(挂结果 + warn-only 不改参)────────────────────


def test_validate_checked_writes_result(tmp_path):
    """清单命中 → status=checked、file 路径正确、unsupported 带 would-warn 项。"""
    _write_supported(tmp_path, "vllm", ["--max-model-len", "--host"])
    traces = {"model": _tv("m"), "max_model_len": _tv(1), "bogus": _tv(2)}
    resolved = _make_resolved(traces)
    validate_engine_params(resolved, tmp_path)

    pv = resolved.param_validation
    assert pv is not None
    assert pv.status == "checked"
    assert pv.policy == "warn_only"
    assert pv.supported_params_file.endswith("engines/vllm/supported_params.txt")
    assert [u["param"] for u in pv.unsupported] == ["bogus"]


def test_validate_missing_file_skips(tmp_path, caplog):
    """清单缺失 → status=skipped_missing_file、不阻塞、WARN 一次、file=None。"""
    traces = {"model": _tv("m"), "whatever": _tv(1)}
    resolved = _make_resolved(traces)
    with caplog.at_level(logging.WARNING):
        validate_engine_params(resolved, tmp_path)  # tmp 无 engines/vllm/supported_params.txt

    pv = resolved.param_validation
    assert pv.status == "skipped_missing_file"
    assert pv.supported_params_file is None
    assert pv.unsupported == []
    assert any("supported_params list is missing or empty" in r.message for r in caplog.records)


def test_validate_is_warn_only_does_not_touch_traces(tmp_path):
    """warn-only:validator 不改 engine_config_traces,argv 逐字节不变(不删参)。"""
    _write_supported(tmp_path, "vllm", ["--max-model-len"])  # bogus 不在清单
    traces = {"model": _tv("m"), "max_model_len": _tv(1), "bogus": _tv(2)}
    resolved = _make_resolved(traces)

    argv_before = build_argv(resolved.engine_config_traces)
    keys_before = list(resolved.engine_config_traces.keys())
    validate_engine_params(resolved, tmp_path)
    argv_after = build_argv(resolved.engine_config_traces)

    assert argv_before == argv_after
    assert list(resolved.engine_config_traces.keys()) == keys_before  # bogus 仍在(未删)
    assert "--bogus" in argv_after


def test_validate_version_layer_path_used(tmp_path):
    """有版本层引擎命中 v{resolved}/ 下清单(决策②路径)。"""
    _write_supported(tmp_path, "sglang", ["--context-length"], version="v0.5.14")
    traces = {"model": _tv("m"), "context_length": _tv(1)}
    resolved = _make_resolved(traces, engine="sglang", resolved_version="v0.5.14", has_version_dir=True)
    validate_engine_params(resolved, tmp_path)

    pv = resolved.param_validation
    assert pv.status == "checked"
    assert pv.supported_params_file.endswith("engines/sglang/v0.5.14/supported_params.txt")
    assert pv.unsupported == []


# ─── multi_node 逐 node 校验(第二步)────────────────────────────────────


def test_validate_standalone_items_have_no_node_key(tmp_path):
    """standalone 结果项**不含** node 键(multi_node 才加,保持 standalone 形态不变)。"""
    _write_supported(tmp_path, "vllm", ["--max-model-len"])
    resolved = _make_resolved({"model": _tv("m"), "bogus": _tv(1)})
    validate_engine_params(resolved, tmp_path)
    assert resolved.param_validation.unsupported[0].get("node") is None


def test_validate_multinode_tags_each_node(tmp_path):
    """multi_node:逐 node 校验,每条 unsupported 带对应 node 标签(head/worker)。"""
    _write_supported(tmp_path, "vllm-ascend", ["--tp"], version="v0.18.0")
    resolved = _make_resolved_multinode(
        [
            ("head", {"model": _tv("m"), "tp": _tv(8), "bad_head": _tv(1)}),
            ("worker", {"model": _tv("m"), "tp": _tv(8), "bad_worker": _tv(1)}),
        ]
    )
    validate_engine_params(resolved, tmp_path)

    pv = resolved.param_validation
    assert pv.status == "checked"
    tagged = {(u["param"], u["node"]) for u in pv.unsupported}
    assert tagged == {("bad_head", "head"), ("bad_worker", "worker")}
    assert pv.supported_params_file.endswith("engines/vllm-ascend/v0.18.0/supported_params.txt")


def test_validate_multinode_all_supported_no_findings(tmp_path):
    """multi_node:各 node 参数全在清单 → 空列表(status=checked)。"""
    _write_supported(tmp_path, "vllm-ascend", ["--tp", "--host"], version="v0.18.0")
    resolved = _make_resolved_multinode(
        [
            ("head", {"model": _tv("m"), "tp": _tv(8), "host": _tv("0.0.0.0")}),
            ("worker", {"model": _tv("m"), "tp": _tv(8)}),
        ]
    )
    validate_engine_params(resolved, tmp_path)
    assert resolved.param_validation.unsupported == []


def test_validate_multinode_missing_file_skips(tmp_path):
    """multi_node + 缺清单 → 同 standalone 走 warn-skip 兜底(不逐 node)。"""
    resolved = _make_resolved_multinode([("head", {"model": _tv("m"), "x": _tv(1)})])
    validate_engine_params(resolved, tmp_path)  # tmp 无清单
    assert resolved.param_validation.status == "skipped_missing_file"


# ─── 真配置端到端(run_pipeline → audit.json + startup_log)───────────────


def test_pipeline_writes_param_validation_to_audit_and_log(
    config_root_real, tmp_path, monkeypatch
):
    """run_pipeline 真配置:audit.json 有 param_validation 块(status=checked),startup_log 有对应行。"""
    hardware_info_path = tmp_path / "hw.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a3", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    log_path = tmp_path / "wings_start.log"
    monkeypatch.setenv("ENGINE_VERSION", "v0.18.0")
    monkeypatch.setenv("WINGS_START_LOG", str(log_path))

    run_pipeline(
        PipelineRequest(
            target=Target(model_name="DeepSeek-V4-Flash", topology=Topology.STANDALONE, engine="vllm-ascend"),
            hardware_info_path=hardware_info_path,
            config_root=config_root_real,
        ),
        output_dir=output_dir,
    )

    audit = json.loads((output_dir / "audit.json").read_text(encoding="utf-8"))
    assert "param_validation" in audit
    pv = audit["param_validation"]
    assert pv["policy"] == "warn_only"
    assert pv["status"] == "checked"
    assert pv["supported_params_file"].endswith("engines/vllm-ascend/v0.18.0/supported_params.txt")
    assert isinstance(pv["unsupported"], list)  # 不锁真配置具体内容(避免与 config 漂移耦合)

    content = log_path.read_text(encoding="utf-8")
    assert "[STARTUP] param_validation policy=warn_only" in content
    assert "status=checked" in content


def test_dry_run_also_invokes_validator(config_root, tmp_path, monkeypatch):
    """--dry-run 路径也调用 validator(dry-run 与 run_pipeline 共用 resolve_pipeline,口径一致)。"""
    import wings_ctl.cli as cli
    import wings_ctl.pipeline as pipeline

    hw = tmp_path / "hw.json"
    hw.write_text(
        json.dumps({"hardware_family": "nvidia-RTX5880", "device": "nvidia", "count": 1}),
        encoding="utf-8",
    )
    called = {"n": 0}
    orig = pipeline.validate_engine_params

    def _spy(resolved, config_root):
        called["n"] += 1
        return orig(resolved, config_root)

    # dry-run 与 run_pipeline 都经 resolve_pipeline 调 validator(pipeline 模块加载时绑定引用)→ pat 此处
    monkeypatch.setattr(pipeline, "validate_engine_params", _spy)
    monkeypatch.setenv("ENGINE_VERSION", "0.19.0")
    monkeypatch.setattr(
        "sys.argv",
        [
            "wings-ctl", "--engine", "vllm", "--model-name", "Qwen3.5-0.8B",
            "--model-path", "/m/Qwen3.5-0.8B", "--config-root", str(config_root),
            "--hardware-info", str(hw), "--dry-run",
        ],
    )
    cli.main()
    assert called["n"] == 1


def test_pipeline_multinode_validates_per_node(config_root_real, tmp_path, monkeypatch):
    """run_pipeline 真配置 multi_node(GLM-4.5/ascend-a2,head+worker):param_validation status=checked。

    资产 vllm-ascend/v0.18.0 在树 → 命中版本层清单;顶层空、逐 node 校验(不因顶层空而漏校)。
    不锁具体 unsupported 内容(避免与 config 漂移耦合),只验分支落到 per-node 且状态正确。
    """
    hardware_info_path = tmp_path / "hw.json"
    hardware_info_path.write_text(
        json.dumps({"hardware_family": "ascend-a2", "device": "ascend", "count": 16}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    monkeypatch.setenv("ENGINE_VERSION", "v0.18.0")
    monkeypatch.setenv("WINGS_START_LOG", str(tmp_path / "wings_start.log"))

    resolved, *_ = run_pipeline(
        PipelineRequest(
            target=Target(model_name="GLM-4.5", topology=Topology.MULTI_NODE, engine="vllm-ascend"),
            hardware_info_path=hardware_info_path,
            config_root=config_root_real,
        ),
        output_dir=output_dir,
    )

    # 前提:确是 multi_node 占位形态(顶层空、nodes 在场)
    assert not resolved.engine_config_traces and resolved.nodes

    audit = json.loads((output_dir / "audit.json").read_text(encoding="utf-8"))
    pv = audit["param_validation"]
    assert pv["status"] == "checked"
    assert pv["supported_params_file"].endswith("engines/vllm-ascend/v0.18.0/supported_params.txt")
    # 若有 unsupported,则每条必带 node 标签(区分是哪个节点)
    for item in pv["unsupported"]:
        assert item.get("node") in {n.role for n in resolved.nodes}
