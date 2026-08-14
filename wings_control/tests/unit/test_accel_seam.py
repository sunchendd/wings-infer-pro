"""wings-accel 输出侧【渲染/审计接缝】单测(stub 测,no-op 安全)。

建议3 / docs/45 §7 落地后,``accel.engine_config`` 改由 **config_resolver** 作为 ``strategy_accel``
合并层并入 ``engine_config_traces``(见 ``tests/integration/test_accel_merge_layer.py``);
**script_builder 不再消费 ``accel.engine_config``**。本文件只覆盖 script_builder / emitter 仍负责的
接缝:``accel.env`` → export 段、``accel.enabled`` → install 段、``accel.audit`` → audit.json;
空 ``AccelResult`` → 零变化(回归)。本接缝与 trace 解耦,直接构造 ``AccelResult`` 作 stub。
"""

from __future__ import annotations

import json

from wings_ctl.accel.smart_accel import AccelResult
from wings_ctl.audit.emitter import emit_audit
from wings_ctl.core.models import (
    EngineVersion,
    HardwareContext,
    ResolvedConfig,
    SourceEvent,
    TracedValue,
)
from wings_ctl.core.topology import Topology
from wings_ctl.rendering.script_builder import build_scripts


def _make_resolved(accel: AccelResult | None = None) -> ResolvedConfig:
    """构造最小可执行 standalone ResolvedConfig;``accel`` 缺省 → 空(回归基线)。

    注:``accel.engine_config`` 不在此注入 traces —— 它由 config_resolver 合并(§7),
    本文件仅验 script_builder/emitter 对 accel.env/enabled/audit 的接缝。
    """
    traces = {
        "model": TracedValue(
            final_value="test-model",
            final_layer="model_scenario",
            source_file="model.yaml",
            source_path="scenarios.standalone.engine_config.model",
            events=[SourceEvent("set", "model_scenario", "test-model", "model.yaml",
                                "scenarios.standalone.engine_config.model")],
        ),
    }
    env_traces = {
        "VLLM_USE_V1": TracedValue(
            final_value="1", final_layer="model_scenario", source_file="model.yaml",
            source_path="scenarios.standalone.env.VLLM_USE_V1",
            events=[SourceEvent("set", "model_scenario", "1", "model.yaml",
                                "scenarios.standalone.env.VLLM_USE_V1")],
        ),
    }
    return ResolvedConfig(
        topology=Topology.STANDALONE,
        hardware=HardwareContext("test-hw", "nvidia", {}),
        engine="vllm",
        engine_version=EngineVersion(requested="0.19.0", resolved="0.19.0", is_fallback=False),
        engine_config_traces=traces,
        env_traces=env_traces,
        source_files=["model.yaml"],
        accel=accel or AccelResult(),
    )


_STUB = AccelResult(
    engine_config={"speculative_config": {"method": "ngram"}},  # 归 config_resolver 合并,script_builder 不读
    env={"WINGS_ACCEL_KV": "on"},
    audit={"smart_decoding_output": {"method": "ngram"}},
    enabled=True,
)


# ── 非空 accel:env 段 + install 段 + audit 被正确接入 ─────────────────────────

def test_build_scripts_wires_accel_env_and_install(tmp_path):
    """验证非空+enabled accel → start_command.sh 含 accel.env export 段 + install 安装段。"""
    start_path, _ = build_scripts(_make_resolved(_STUB), tmp_path)
    start_text = start_path.read_text(encoding="utf-8")
    assert "export WINGS_ACCEL_KV=on" in start_text            # accel.env 进 env 段
    # enabled=True → install 段(new --config JSON 形式;_STUB 未声明依赖 → packages=[])
    assert "install.py --config" in start_text
    assert '"engine": {"name": "vllm", "version": "v0.19.0"}' in start_text
    assert '"packages": []' in start_text
    # script_builder 不再消费 accel.engine_config(改由 config_resolver 合并 → 不在 traces 就不出现)
    assert "--speculative-config" not in start_text


def test_repro_wires_accel_env_section(tmp_path):
    """验证非空 accel → repro.sh 含独立的 wings-accel env 段。"""
    _, repro_path = build_scripts(_make_resolved(_STUB), tmp_path)
    repro_text = repro_path.read_text(encoding="utf-8")
    assert "Environment Variables (wings-accel)" in repro_text  # 独立 env 段
    assert "export WINGS_ACCEL_KV=on" in repro_text


def test_build_scripts_wires_pre_serve_and_master_only(tmp_path):
    """KV 存储后端 accel:pre_serve(所有节点)+ pre_serve_master(仅 master)+ pre_serve_client(仅 client)接入 start_command.sh。

    master-only 段用 RANK_IP==MASTER_IP 运行时条件包裹 daemon(单机 MASTER_IP 未设 → 条件真 → 起 daemon);
    client-only 段用逆条件 RANK_IP!=MASTER_IP 包裹(单机 MASTER_IP 未设 → 条件假 → 不跑,单机即 master)。
    """
    accel = AccelResult(
        env={"MOONCAKE_CONFIG_PATH": "/shared-volume/mooncake.json"},
        enabled=True,
        pre_serve=["cat > /shared-volume/mooncake.json <<EOF", "EOF"],
        pre_serve_master=["mooncake_master --port 50088 &"],
        pre_serve_client=["cat > /shared-volume/worker_only.conf <<EOF", "EOF"],
    )
    start_path, repro_path = build_scripts(_make_resolved(accel), tmp_path)
    text = start_path.read_text(encoding="utf-8")
    # 所有节点段(生成配置)
    assert "KV store pre-serve (all nodes)" in text
    assert "cat > /shared-volume/mooncake.json <<EOF" in text
    # master-only 段:条件包裹 daemon
    assert "KV store pre-serve (master only)" in text
    assert 'if [ -z "${MASTER_IP:-}" ] || [ "${RANK_IP:-}" = "${MASTER_IP:-}" ]; then' in text
    assert "    mooncake_master --port 50088 &" in text
    assert text.index("\nfi\n") > text.index("mooncake_master")  # 关闭 fi 在 daemon 之后(勿被 pipefail 误命中)
    # client-only 段:逆条件包裹(RANK_IP != MASTER_IP)
    assert "KV store pre-serve (client only)" in text
    assert 'if [ -n "${MASTER_IP:-}" ] && [ "${RANK_IP:-}" != "${MASTER_IP:-}" ]; then' in text
    assert "    cat > /shared-volume/worker_only.conf <<EOF" in text
    # pre_serve 段位于 install 段之后、引擎命令之前(后台化,无 exec 前缀)
    assert text.index("KV store pre-serve") > text.index("install.py --config")
    assert text.rindex("vllm serve") > text.index("KV store pre-serve")
    # repro.sh 同步渲染(master + client 段)
    repro_text = repro_path.read_text(encoding="utf-8")
    assert "KV store pre-serve (master only)" in repro_text
    assert "KV store pre-serve (client only)" in repro_text


def test_empty_accel_no_pre_serve_section(tmp_path):
    """空 accel / 非 KV 后端 → start_command.sh 不含 pre_serve 段(零影响回归)。"""
    start_path, _ = build_scripts(_make_resolved(), tmp_path)
    assert "KV store pre-serve" not in start_path.read_text(encoding="utf-8")


# ── advanced_features.json 写入(使能状态单一真相源,health /v1/startup/accel 读它)──

def _accel_full(size_gb: int) -> AccelResult:
    """构造 auto 生效的 accel stub(投机+卸载选中,kv 容量=估算值)。"""
    return AccelResult(
        enabled=True,
        kv_mem_offload_size_gb=size_gb,
        audit={"smart_decoding_scheme": "mtp", "smart_kv_cache_scheme": "cpu"},
    )


def test_build_scripts_writes_advanced_features_auto_size(tmp_path, monkeypatch):
    """auto 生效 → advanced_features.json 的 others.kv_mem_offload_size 填估算值(页面回显口径)。"""
    import json as _json
    from wings_ctl.common.settings import settings

    target = tmp_path / "advanced_features.json"
    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(target))
    build_scripts(_make_resolved(_accel_full(401)), tmp_path)

    data = _json.loads(target.read_text(encoding="utf-8"))
    assert data["engine"] == "vllm"
    assert data["features"] == {
        "speculative_decode": True, "sparse_kv": False, "kv_offload": True, "rag_acc": False,
    }
    assert data["variants"]["speculative_decode"] == "mtp"
    assert data["variants"]["kv_offload"] == "cpu"
    assert data["others"]["kv_mem_offload_size"] == 401  # auto 估算值(512-59-51.2→401)


def test_build_scripts_writes_advanced_features_disabled(tmp_path, monkeypatch):
    """全关 accel → features 全 false,kv_mem_offload_size=null(无有效容量)。"""
    import json as _json
    from wings_ctl.common.settings import settings

    target = tmp_path / "advanced_features.json"
    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(target))
    build_scripts(_make_resolved(AccelResult()), tmp_path)

    data = _json.loads(target.read_text(encoding="utf-8"))
    assert data["features"]["kv_offload"] is False
    assert data["variants"]["kv_offload"] is None
    assert data["others"]["kv_mem_offload_size"] is None  # 未请求 → null
    assert data["others"]["speculative_decode"] is None


def test_emit_audit_writes_wings_accel(tmp_path):
    """验证非空 accel.audit → audit.json 写入 wings_accel 诊断块。"""
    audit_path = emit_audit(_make_resolved(_STUB), tmp_path)
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert data["wings_accel"] == {"smart_decoding_output": {"method": "ngram"}}


def test_emit_audit_writes_diagnostics(tmp_path):
    """验证 accel.audit 含 diagnostics(降级信息)→ 原样落 audit.json 的 wings_accel 段(docs/45 §6)。"""
    accel = AccelResult(
        engine_config={"speculative_config": {"method": "suffix"}},
        audit={
            "smart_decoding_scheme": "suffix",
            "diagnostics": {"decoding": {"degraded": True, "degrade_reason": "mtp_conflict->suffix"}},
        },
        enabled=True,
    )
    audit_path = emit_audit(_make_resolved(accel), tmp_path)
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert data["wings_accel"]["smart_decoding_scheme"] == "suffix"
    assert data["wings_accel"]["diagnostics"] == {
        "decoding": {"degraded": True, "degrade_reason": "mtp_conflict->suffix"}
    }


# ── 空 accel:零变化(回归)──────────────────────────────────────────────────

def test_empty_accel_no_argv_or_env_change(tmp_path):
    """验证空 AccelResult(默认/未接通)→ 脚本不含任何 wings-accel 痕迹 + 无 install 段(no-op 回归)。"""
    start_path, repro_path = build_scripts(_make_resolved(), tmp_path)
    start_text = start_path.read_text(encoding="utf-8")
    repro_text = repro_path.read_text(encoding="utf-8")
    assert "WINGS_ACCEL_KV" not in start_text and "install.py" not in start_text
    assert "(wings-accel)" not in repro_text


def test_empty_accel_no_audit_key(tmp_path):
    """验证空 accel.audit → audit.json 不含 wings_accel 键(no-op 回归)。"""
    audit_path = emit_audit(_make_resolved(), tmp_path)
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert "wings_accel" not in data
