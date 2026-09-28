"""wings-accel 输出侧【渲染/审计接缝】单测(stub 测,no-op 安全)。

建议3 / docs/45 §7 落地后,``accel.engine_config`` 改由 **config_resolver** 作为 ``strategy_accel``
合并层并入 ``engine_config_traces``(见 ``tests/integration/test_accel_merge_layer.py``);
``accel.env`` 同样由 resolver 并入 ``env_traces``。本文件只覆盖 script_builder / emitter 仍负责的
接缝:trace → export 段、``accel.enabled`` → install 段、``accel.audit`` → audit.json;
空 ``AccelResult`` → 零变化(回归)。本接缝与 trace 解耦,直接构造 ``AccelResult`` 作 stub。
"""

from __future__ import annotations

import json

import pytest

from wings_ctl.accel.smart_accel import AccelResult, GeneratedFileSpec
from wings_ctl.audit.emitter import emit_audit
from wings_ctl.core.config_resolver import MergeLayer, trace_merge
from wings_ctl.core.models import (
    EngineVersion,
    HardwareContext,
    ResolvedConfig,
    SourceEvent,
    TracedValue,
)
from wings_ctl.core.topology import Topology
from wings_ctl.rendering import script_builder
from wings_ctl.rendering.script_builder import build_scripts


def _make_resolved(accel: AccelResult | None = None) -> ResolvedConfig:
    """构造最小可执行 standalone ResolvedConfig;``accel`` 缺省 → 空(回归基线)。

    注:生产路径由 config_resolver 合并 accel engine_config/env；夹具只模拟 env 的已解析结果。
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
    env_layers = [MergeLayer("model_scenario", {"VLLM_USE_V1": "1"}, "model.yaml", "scenarios.standalone.env")]
    if accel and accel.env:
        env_layers.append(MergeLayer("strategy_accel", accel.env, "<wings-accel>", "strategy.accel.env"))
    env_traces = trace_merge(env_layers)
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


def test_repro_renders_accel_env_from_trace(tmp_path):
    """验证 accel env 由统一 trace 段渲染，不再生成独立重复区块。"""
    _, repro_path = build_scripts(_make_resolved(_STUB), tmp_path)
    repro_text = repro_path.read_text(encoding="utf-8")
    assert "Environment Variables (wings-accel)" not in repro_text
    assert "# source: <wings-accel> @ strategy.accel.env.WINGS_ACCEL_KV" in repro_text
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
    monkeypatch.setenv("RAG_ACC_ENABLED", "true")
    build_scripts(_make_resolved(_accel_full(401)), tmp_path)

    data = _json.loads(target.read_text(encoding="utf-8"))
    assert data["engine"] == "vllm"
    assert data["features"] == {
        "speculative_decode": True, "sparse_kv": False, "kv_offload": True, "rag_acc": False,
        # 本地卸载场景:kv_offload(合一口径)true,但显式分布式标志 false
        "kv_distributed_offload": False,
    }
    assert data["variants"]["speculative_decode"] == "mtp"
    assert data["variants"]["kv_offload"] == "cpu"
    assert data["variants"]["kv_distributed_offload"] is None
    assert data["others"]["kv_mem_offload_size"] == 401  # auto 估算值(512-59-51.2→401)


def test_build_scripts_reports_rag_acc_from_resolved_env(tmp_path, monkeypatch):
    import json as _json
    from wings_ctl.common.settings import settings

    target = tmp_path / "advanced_features.json"
    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(target))
    resolved = _make_resolved()
    resolved.env_traces["RAG_ACC_ENABLED"] = TracedValue(
        final_value="true",
        final_layer="feature_inject",
        source_file="<feature-inject>",
        source_path="feature.rag_acc",
        events=[],
    )

    start_path, _ = build_scripts(resolved, tmp_path)

    assert "export RAG_ACC_ENABLED=true" in start_path.read_text(encoding="utf-8")
    data = _json.loads(target.read_text(encoding="utf-8"))
    assert data["features"]["rag_acc"] is True

    import asyncio
    from wings_ctl.proxy import health_service

    response = asyncio.run(health_service.get_startup_accel())
    payload = _json.loads(response.body)
    assert payload["data"]["features"]["rag_acc"] is True


def test_build_scripts_reports_explicitly_disabled_rag_acc(tmp_path, monkeypatch):
    import json as _json
    from wings_ctl.common.settings import settings

    target = tmp_path / "advanced_features.json"
    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(target))
    monkeypatch.setenv("RAG_ACC_ENABLED", "true")
    resolved = _make_resolved()
    resolved.env_traces["RAG_ACC_ENABLED"] = TracedValue(
        final_value="false",
        final_layer="feature_inject",
        source_file="<feature-inject>",
        source_path="feature.rag_acc",
        events=[],
    )

    start_path, _ = build_scripts(resolved, tmp_path)

    assert "export RAG_ACC_ENABLED=false" in start_path.read_text(encoding="utf-8")
    data = _json.loads(target.read_text(encoding="utf-8"))
    assert data["features"]["rag_acc"] is False


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


def test_build_scripts_reports_sparse_scheme_as_sparse_kv(tmp_path, monkeypatch):
    """MaaS 开 SPARSE 且命中 yaml scheme → 页面回显稀疏；纯 recipe fp8（未开 SPARSE）不算。"""
    import json as _json
    from wings_ctl.common.settings import settings

    target = tmp_path / "advanced_features.json"
    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(target))
    resolved = _make_resolved()
    resolved.engine_config_traces["kv_cache_dtype"] = TracedValue(
        final_value="fp8", final_layer="model_scenario", source_file="model.yaml",
        source_path="scenarios.standalone.engine_config.kv_cache_dtype", events=[],
    )
    build_scripts(resolved, tmp_path)

    data = _json.loads(target.read_text(encoding="utf-8"))
    # 无选中 sparse scheme（SPARSE 未开/未命中）→ 即使 recipe 基线是 fp8 也不回显稀疏
    assert data["features"]["sparse_kv"] is False
    assert data["variants"]["sparse_kv"] is None


def test_build_scripts_does_not_report_fp8_e4m3_as_sparse(tmp_path, monkeypatch):
    """仅选中 sparse scheme 才回显稀疏；fp8_e4m3 等其他 dtype 不影响该口径。"""
    import json as _json
    from wings_ctl.common.settings import settings

    target = tmp_path / "advanced_features.json"
    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(target))
    resolved = _make_resolved()
    resolved.engine_config_traces["kv_cache_dtype"] = TracedValue(
        final_value="fp8_e4m3", final_layer="model_scenario", source_file="model.yaml",
        source_path="scenarios.standalone.engine_config.kv_cache_dtype", events=[],
    )
    build_scripts(resolved, tmp_path)

    data = _json.loads(target.read_text(encoding="utf-8"))
    assert data["features"]["sparse_kv"] is False


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


# ── wings-accel 文件计划写入(解析期不落盘,产物阶段原子写)──────────────────────

def test_build_scripts_writes_accel_generated_files(tmp_path, monkeypatch):
    """accel.generated_files 非空 → build_scripts 原子写入共享卷文件(content + mode)。"""
    from wings_ctl.common.settings import settings

    shared = tmp_path / "shared"
    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(shared))
    accel = AccelResult(
        enabled=True,
        generated_files=[
            GeneratedFileSpec(
                path=str(shared / "lmcache_config.yaml"),
                content="chunk_size: 256\nlocal_disk: /mnt/kv\n",
                mode="0644",
                scope="all",
            ),
            GeneratedFileSpec(
                path=str(shared / "start_kv_serve.sh"),
                content="#!/bin/bash\n",
                mode="0755",
                scope="master",
            ),
        ],
    )
    build_scripts(_make_resolved(accel), tmp_path)

    lmcache = shared / "lmcache_config.yaml"
    assert lmcache.read_text(encoding="utf-8") == "chunk_size: 256\nlocal_disk: /mnt/kv\n"
    assert lmcache.stat().st_mode & 0o777 == 0o644
    daemon = shared / "start_kv_serve.sh"
    assert daemon.read_text(encoding="utf-8") == "#!/bin/bash\n"
    assert daemon.stat().st_mode & 0o777 == 0o755
    # 原子写不留 .tmp 残留
    assert not [item for item in shared.iterdir() if item.name.endswith(".tmp")]


def test_build_scripts_rejects_generated_file_outside_shared_volume(tmp_path, monkeypatch):
    """文件计划越出共享卷根 → fail-fast(ValueError,安全边界不静默)。"""
    from wings_ctl.common.settings import settings

    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(tmp_path / "shared"))
    accel = AccelResult(
        enabled=True,
        generated_files=[GeneratedFileSpec(path="/etc/passwd", content="evil\n", mode="0644", scope="all")],
    )
    with pytest.raises(ValueError):
        build_scripts(_make_resolved(accel), tmp_path)


def test_build_scripts_fails_when_generated_file_cannot_be_written(tmp_path, monkeypatch):
    """生成文件写入失败必须阻断启动，不能只记录 warning 后继续交付脚本。"""
    from wings_ctl.common.settings import settings

    shared = tmp_path / "shared"
    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(shared))
    accel = AccelResult(
        enabled=True,
        generated_files=[
            GeneratedFileSpec(
                path=str(shared / "lmcache_config.yaml"),
                content="chunk_size: 256\n",
            )
        ],
    )

    def fail_named_temp_file(*args, **kwargs):
        raise OSError("read-only shared volume")

    monkeypatch.setattr(script_builder.tempfile, "NamedTemporaryFile", fail_named_temp_file)

    with pytest.raises(ValueError, match="failed to write accel generated file"):
        build_scripts(_make_resolved(accel), tmp_path)


def test_build_scripts_empty_generated_files_is_noop(tmp_path, monkeypatch):
    """空 accel / 无 generated_files → 不写任何文件(no-op 回归)。"""
    from wings_ctl.common.settings import settings

    shared = tmp_path / "shared"
    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(shared))
    build_scripts(_make_resolved(), tmp_path)
    assert not shared.exists() or not any(shared.iterdir())


def test_build_scripts_installs_mooncake_script_assets(tmp_path, monkeypatch):
    """脚本兜底被选中时，受控 mooncake 目录应完整复制到共享卷。"""
    from wings_ctl.common.settings import settings

    shared = tmp_path / "shared"
    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(shared))
    accel = AccelResult(
        enabled=True,
        mooncake_script_assets_required=True,
        pre_serve=[
            'source "$SHARED_VOLUME_PATH/mooncake/client.env"',
            'bash "$SHARED_VOLUME_PATH/mooncake/creat_mooncake_json.sh"',
            'bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_store.sh" &',
        ],
        mooncake_master_section=[
            "# ─── Mooncake master branch (IS_MOONCAKE_MASTER) ───",
            'if [ "${IS_MOONCAKE_MASTER:-}" = "TRUE" ] || [ "${IS_MOONCAKE_MASTER:-}" = "true" ] || \\',
            '   [ "${IS_MOONCAKE_MASTER:-}" = "1" ] || [ "${IS_MOONCAKE_MASTER:-}" = "True" ]; then',
            '    source "$SHARED_VOLUME_PATH/mooncake/master.env"',
            '    mkdir -p /var/log/wings',
            '    bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_master.sh" &',
            "    MASTER_PID=$!",
            '    _wings_log INFO "mooncake master started, PID=$MASTER_PID"',
            '    wait "$MASTER_PID"',
            '    exit "$?"',
            "fi",
            "",
        ],
    )

    start_path, _ = build_scripts(_make_resolved(accel), tmp_path)

    target = shared / "mooncake"
    assert (target / "creat_mooncake_json.sh").is_file()
    assert (target / "client.env").is_file()
    assert (target / "env.yaml").is_file()
    assert (target / "start_mooncake_store.sh").is_file()
    assert (target / "start_mooncake_master.sh").is_file()
    assert (target / "mooncake_store.py").is_file()
    assert (target / "master.env").is_file()
    start_text = start_path.read_text(encoding="utf-8")
    assert "$SHARED_VOLUME_PATH/mooncake/creat_mooncake_json.sh" in start_text
    assert 'source "$SHARED_VOLUME_PATH/mooncake/client.env"' in start_text
    assert "$SHARED_VOLUME_PATH/mooncake/start_mooncake_store.sh" in start_text
    assert "IS_MOONCAKE_MASTER" in start_text
    assert "$SHARED_VOLUME_PATH/mooncake/start_mooncake_master.sh" in start_text


def test_install_mooncake_script_assets_fails_fast_on_pyc_only_assets(
    tmp_path, monkeypatch
):
    """资产源只剩 mooncake_store.pyc(旧镜像未在加密前拷出资产)必须 fail-fast。

    场景:MOONCAKE_ASSETS_PATH 指向的目录只有 .pyc 没有 .py —— 说明镜像用旧
    Dockerfile 构建,.py 已被加密步骤删除;若此时静默拷贝,.pyc 会进入共享卷,
    engine 容器执行 start_mooncake_store.sh 时才以 file not found / bad magic
    number 失败。生成期抛 ValueError,把故障拦在产物阶段。
    """
    from wings_ctl.common.settings import settings

    shared = tmp_path / "shared"
    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(shared))
    stale = tmp_path / "stale_assets"
    stale.mkdir()
    (stale / "mooncake_store.pyc").write_bytes(b"\x00compiled")
    (stale / "start_mooncake_store.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setenv("MOONCAKE_ASSETS_PATH", str(stale))

    accel = AccelResult(enabled=True, mooncake_script_assets_required=True)
    with pytest.raises(ValueError, match="mooncake_store.py"):
        build_scripts(_make_resolved(accel), tmp_path)
    assert not (shared / "mooncake").exists()


def test_write_mooncake_master_env_renders_defaults_and_maas_override(tmp_path, monkeypatch):
    """master.env 由 env.yaml 默认值 + MaaS 同名 env 覆盖渲染;覆盖值必须落到文件。"""
    from wings_ctl.common.settings import settings
    from wings_ctl.rendering.script_builder import _write_mooncake_master_env

    shared = tmp_path / "shared"
    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(shared))
    monkeypatch.setenv("MOONCAKE_MASTER_PORT", "50099")
    monkeypatch.setenv("MOONCAKE_MASTER_DEFAULT_KV_LEASE_TTL", "22000")

    _write_mooncake_master_env()

    content = (shared / "mooncake" / "master.env").read_text(encoding="utf-8")
    assert "export MOONCAKE_MASTER_PORT=50099" in content
    assert "export MOONCAKE_MASTER_DEFAULT_KV_LEASE_TTL=22000" in content
    # 未被 MaaS 覆盖的变量保留 env.yaml 默认值
    assert "export MOONCAKE_MASTER_EVICTION_HIGH_WATERMARK_RATIO=0.9" in content
    assert "export MOONCAKE_MASTER_EVICTION_RATIO=0.1" in content
    assert "export MOONCAKE_MASTER_LOG_PATH=/var/log/wings" in content


# ── 分布式 auto 智能推荐:解析值注入 client.env(覆盖原始 "auto" 字面量)──


def test_write_mooncake_client_env_accel_override_beats_maas_raw(tmp_path, monkeypatch):
    """accel 解析值(估算)为最高覆盖层:MaaS 原始 auto 字面量不得落进 client.env。"""
    from wings_ctl.common.settings import settings
    from wings_ctl.rendering.script_builder import _write_mooncake_client_env

    shared = tmp_path / "shared"
    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(shared))
    monkeypatch.setenv("KV_MEM_OFFLOAD_SIZE", "auto")
    monkeypatch.setenv("KV_PROTOCOL", "rdma")

    _write_mooncake_client_env({"KV_MEM_OFFLOAD_SIZE": "171"})

    content = (shared / "mooncake" / "client.env").read_text(encoding="utf-8")
    assert "export KV_MEM_OFFLOAD_SIZE=171" in content
    assert "auto" not in content  # 原始 "auto" 字面量被估算值替换(脚本侧只认纯数值)
    assert "export KV_PROTOCOL=rdma" in content  # 其余变量仍走 env.yaml + MaaS 链路


def test_build_scripts_injects_resolved_size_into_mooncake_env(tmp_path, monkeypatch):
    """build_scripts 端到端:kv_mem_offload_size_gb=171(auto 估算)→ client/master.env 落 171。"""
    from wings_ctl.common.settings import settings

    shared = tmp_path / "shared"
    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(shared))
    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(tmp_path / "advanced_features.json"))
    monkeypatch.setenv("KV_MEM_OFFLOAD_SIZE", "auto")
    accel = AccelResult(
        enabled=True,
        kv_mem_offload_size_gb=171,
        mooncake_script_assets_required=True,
        audit={"smart_distributed_kv_cache_scheme": "mooncake_standalone_store"},
        pre_serve=['bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_store.sh" &'],
    )

    build_scripts(_make_resolved(accel), tmp_path)

    client = (shared / "mooncake" / "client.env").read_text(encoding="utf-8")
    master = (shared / "mooncake" / "master.env").read_text(encoding="utf-8")
    assert "export KV_MEM_OFFLOAD_SIZE=171" in client
    assert "export KV_MEM_OFFLOAD_SIZE=171" in master


def test_build_scripts_writes_advanced_features_distributed_size(tmp_path, monkeypatch):
    """分布式 auto 生效 → kv_offload feature 回显 true + others.kv_mem_offload_size=估算值。"""
    import json as _json
    from wings_ctl.common.settings import settings

    target = tmp_path / "advanced_features.json"
    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(target))
    accel = AccelResult(
        enabled=True,
        kv_mem_offload_size_gb=171,
        audit={"smart_distributed_kv_cache_scheme": "mooncake_standalone_store"},
    )
    build_scripts(_make_resolved(accel), tmp_path)

    data = _json.loads(target.read_text(encoding="utf-8"))
    assert data["features"]["kv_offload"] is True
    assert data["features"]["kv_distributed_offload"] is True  # MaaS 前端消费的显式分布式标志
    assert data["variants"]["kv_offload"] == "mooncake_standalone_store"
    assert data["variants"]["kv_distributed_offload"] == "mooncake_standalone_store"
    assert data["others"]["kv_mem_offload_size"] == 171


# ── master Pod 身份兜底:特性未生效(降级/未开)也绝不回退执行 vllm serve ──


def test_master_pod_holds_when_feature_not_effective(tmp_path, monkeypatch):
    """master Pod + 特性降级(空 accel)→ 专属交付支线:挂起分支,全文无任何引擎命令。"""
    from wings_ctl.common.settings import settings

    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(tmp_path / "advanced_features.json"))
    monkeypatch.setenv("IS_MOONCAKE_MASTER", "true")

    start_path, _ = build_scripts(_make_resolved(), tmp_path)  # 空 AccelResult = 特性降级形态

    text = start_path.read_text(encoding="utf-8")
    # 挂起分支存在:ERROR 日志说明原因 + 无限等待
    assert 'if [ "${IS_MOONCAKE_MASTER:-}" = "TRUE" ]' in text
    assert "distributed KV offload is NOT effective" in text
    assert "while true; do sleep 3600; done" in text
    # 专属交付支线比旧"分支拦截在引擎命令之前"更强:脚本全文不存在任何引擎命令行
    # (master Pod 在任何情况下都不承担推理职责,连 vllm argv 都不渲染;hold 段日志
    # 文本里的 "vllm serve" 字样不是命令)。
    engine_lines = [ln for ln in text.splitlines() if ln.lstrip().startswith("vllm serve")]
    assert not engine_lines
    # 交付支线不注入 install.py / log_analyzer
    assert "install.py" not in text
    assert "log_analyzer" not in text
    # 防御尾:IS_MOONCAKE_MASTER 未命中时显式失败,不静默成功
    assert "reached end without IS_MOONCAKE_MASTER match" in text
    # 回显(降级形态):kv_distributed_offload(MaaS 前端消费字段)显式 false,
    # kv_offload 合一口径同为 false;空 AccelResult 下容量为 None(无有效容量)。
    degraded = json.loads(
        (tmp_path / "advanced_features.json").read_text(encoding="utf-8")
    )
    assert degraded["features"]["kv_distributed_offload"] is False
    assert degraded["variants"]["kv_distributed_offload"] is None
    assert degraded["features"]["kv_offload"] is False
    assert degraded["others"]["kv_mem_offload_size"] is None


def test_master_pod_prefers_feature_section_when_active(tmp_path, monkeypatch):
    """master Pod + 特性生效(accel 产出 master 段)→ 专属交付支线。

    install 段(仅传输引擎包,mooncake_master 二进制来源)先于产出段,资产/env 文件照常落盘,不注入 log_analyzer / 引擎命令。
    """
    from wings_ctl.common.settings import settings

    shared = tmp_path / "shared"
    monkeypatch.setattr(settings, "SHARED_VOLUME_PATH", str(shared))
    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(tmp_path / "advanced_features.json"))
    monkeypatch.setenv("IS_MOONCAKE_MASTER", "true")
    accel = AccelResult(
        enabled=True,
        mooncake_script_assets_required=True,
        kv_mem_offload_size_gb=64,
        mooncake_transfer_engine_package="xcache_cuda:v0.3.12.post1",
        mooncake_master_section=[
            "# ─── Mooncake master branch (IS_MOONCAKE_MASTER) ───",
            'if [ "${IS_MOONCAKE_MASTER:-}" = "TRUE" ]; then',
            '    bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_master.sh" &',
            '    wait "$!"',
            '    exit "$?"',
            "fi",
        ],
    )

    start_path, repro_path = build_scripts(_make_resolved(accel), tmp_path)

    text = start_path.read_text(encoding="utf-8")
    assert "start_mooncake_master.sh" in text
    assert "NOT effective" not in text  # 挂起兜底段不出现
    # install 段只含传输引擎包(不装引擎依赖包),且先于 master 分支段(与 engine Pod 段序一致)
    assert 'install.py --config' in text
    assert '"packages": ["xcache_cuda:v0.3.12.post1"]' in text
    assert text.index("install.py --config") < text.index("start_mooncake_master.sh")
    # 交付支线不注入分析器 / 引擎命令
    assert "log_analyzer" not in text
    engine_lines = [ln for ln in text.splitlines() if ln.lstrip().startswith("vllm serve")]
    assert not engine_lines
    # mooncake 资产 + env 文件照常落盘;KV_MEM_OFFLOAD_SIZE 解析值覆盖原始 auto 字面量
    assert (shared / "mooncake" / "start_mooncake_master.sh").is_file()
    assert (shared / "mooncake" / "master.env").is_file()
    assert "export KV_MEM_OFFLOAD_SIZE=64" in (shared / "mooncake" / "master.env").read_text(encoding="utf-8")
    # repro 同构(附来源头注释)
    repro_text = repro_path.read_text(encoding="utf-8")
    assert "start_mooncake_master.sh" in repro_text
    assert "Reproducibility Script (mooncake master pod delivery)" in repro_text


def test_master_pod_skips_install_when_transfer_engine_not_injected(tmp_path, monkeypatch):
    """master Pod + 特性生效但传输引擎包未注入(ENABLE_XCACHE_INSTALL=false)→ 不渲染 install 段。

    由镜像预装的 mooncake_master 兜底,与 engine Pod 同开关语义。
    """
    from wings_ctl.common.settings import settings

    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(tmp_path / "advanced_features.json"))
    monkeypatch.setenv("IS_MOONCAKE_MASTER", "true")
    accel = AccelResult(
        enabled=True,
        mooncake_script_assets_required=True,
        mooncake_master_section=[
            'if [ "${IS_MOONCAKE_MASTER:-}" = "TRUE" ]; then',
            '    bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_master.sh" &',
            "fi",
        ],
    )

    start_path, _ = build_scripts(_make_resolved(accel), tmp_path)

    text = start_path.read_text(encoding="utf-8")
    assert "start_mooncake_master.sh" in text
    assert "install.py" not in text


def test_mooncake_master_pod_delivery_precedes_placeholder_view(tmp_path, monkeypatch):
    """master Pod 的 resolve 形态是 multi_node 占位视图(nodes 非空,无运行时上下文):交付支线必须先于占位检查,否则得到 exit 3 的占位脚本,资产与 master 分支都不会产出。"""
    from wings_ctl.common.settings import settings

    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(tmp_path / "advanced_features.json"))
    monkeypatch.setenv("IS_MOONCAKE_MASTER", "true")
    accel = AccelResult(
        enabled=True,
        mooncake_script_assets_required=True,
        mooncake_master_section=[
            'if [ "${IS_MOONCAKE_MASTER:-}" = "TRUE" ]; then',
            '    bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_master.sh" &',
            "fi",
        ],
    )
    resolved = _make_resolved(accel)
    # 模拟 master Pod 上 resolve 的真实产物:nodes 非空(占位视图)。
    resolved.nodes = [
        type("ResolvedNodeStub", (), {
            "role": "head", "index": 0,
            "engine_config_traces": {}, "env_traces": {},
            "system_setup": None, "source_prefix": "nodes[0]",
        })(),
    ]

    start_path, _ = build_scripts(resolved, tmp_path)

    text = start_path.read_text(encoding="utf-8")
    # 不是占位脚本;是 master 交付脚本
    assert "MULTI-NODE — RUNTIME INJECTION PENDING" not in text
    assert "start_mooncake_master.sh" in text
    assert "exit 3" not in text


def test_non_master_pod_renders_no_master_branch(tmp_path, monkeypatch):
    """普通引擎 Pod(无 IS_MOONCAKE_MASTER)→ 不渲染任何 master 分支(零影响回归)。"""
    from wings_ctl.common.settings import settings

    monkeypatch.setattr(settings, "ADVANCED_FEATURES_FILE", str(tmp_path / "advanced_features.json"))
    monkeypatch.delenv("IS_MOONCAKE_MASTER", raising=False)

    start_path, _ = build_scripts(_make_resolved(), tmp_path)

    assert "IS_MOONCAKE_MASTER" not in start_path.read_text(encoding="utf-8")


def test_emit_audit_records_accel_generated_files(tmp_path):
    """audit.json 记录 accel 文件计划元数据 + sha256 摘要,不落原始 content。"""
    accel = AccelResult(
        enabled=True,
        generated_files=[
            GeneratedFileSpec(
                path="/shared-volume/lmcache_config.yaml",
                content="chunk_size: 256\n",
                mode="0644",
                scope="all",
                source_file="model.yaml",
                source_path="smart_accel.kv_offload[0].files[0]",
            ),
        ],
    )
    audit_path = emit_audit(_make_resolved(accel), tmp_path)
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    entry = data["accel_generated_files"][0]
    assert entry["path"] == "/shared-volume/lmcache_config.yaml"
    assert entry["mode"] == "0644"
    assert entry["scope"] == "all"
    assert entry["source_file"] == "model.yaml"
    assert entry["source_path"] == "smart_accel.kv_offload[0].files[0]"
    assert "content" not in entry          # 不落原始内容
    assert len(entry["sha256"]) == 64      # sha256 十六进制摘要


def test_emit_audit_empty_generated_files_no_key(tmp_path):
    """空 accel.generated_files → audit.json 不含 accel_generated_files 键(no-op 回归)。"""
    audit_path = emit_audit(_make_resolved(), tmp_path)
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert "accel_generated_files" not in data


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


# ── KV 磁盘卸载残留清理(服务重启后旧数据超规划容量)─────────────────────────

def test_kv_disk_cleanup_rendered_before_serve(tmp_path):
    """disk 开启(kv_disk_offload_path 非空)→ start_command.sh 在 vllm serve 前清空 <path>/*。

    背景:LMCache disk 卸载数据落盘在 KV_DISK_OFFLOAD_PATH 下,服务重启后旧数据
    残留会超出 MaaS 规划容量(KV_DISK_OFFLOAD_SIZE),启动前清空保证占用与规划一致。
    """
    accel = AccelResult(
        env={"LMCACHE_LOCAL_DISK": "/lm"},
        enabled=True,
        kv_disk_offload_path="/lm",
    )
    start_path, repro_path = build_scripts(_make_resolved(accel), tmp_path)
    start_text = start_path.read_text(encoding="utf-8")
    assert "mkdir -p /lm" in start_text
    assert "rm -f /lm/*.pt" in start_text
    # 清理段必须在 vllm serve 之前(先清残留再启动引擎)
    assert start_text.index("rm -f /lm/*.pt") < start_text.index("vllm serve")
    # repro.sh 同款清理(复现也需要干净基线)
    assert "rm -f /lm/*.pt" in repro_path.read_text(encoding="utf-8")


def test_kv_disk_cleanup_absent_without_disk(tmp_path):
    """无磁盘卸载(kv_disk_offload_path=None,含 mem-only / accel 关)→ 不渲染清理段(no-op 回归)。"""
    accel = AccelResult(env={"LMCACHE_LOCAL_CPU": "True"}, enabled=True)  # mem-only,path None
    start_path, repro_path = build_scripts(_make_resolved(accel), tmp_path)
    start_text = start_path.read_text(encoding="utf-8")
    assert "kvcache" not in start_text
    assert "rm -rf" not in start_text
    assert "rm -rf" not in repro_path.read_text(encoding="utf-8")

# ── 部署进度 guard:标准路径先校验后落盘,失败不留半成品 ──────────────

def test_standard_path_guard_failure_writes_no_scripts(monkeypatch, tmp_path):
    """标准 standalone 路径:analyzer preamble 缺失 → guard 在落盘前失败,
    不留下未通过校验的 start_command.sh / repro.sh。"""
    # 让前置 preamble 返回 None → start_content 缺 log_analyzer 片段 → guard 失败
    monkeypatch.setattr(script_builder, "_build_analyzer_preamble", lambda _resolved: None)

    with pytest.raises(ValueError):
        build_scripts(_make_resolved(), tmp_path)

    assert not (tmp_path / "start_command.sh").exists()
    assert not (tmp_path / "repro.sh").exists()


# ── install.py 包预检:镜像与代码版本漂移在生成期暴露 ───────────────────────

def test_validate_accel_packages_preflight(tmp_path, monkeypatch):
    """生成期预检:工件在 → 按目录名精确匹配;缺版本 → ValueError;工件缺 → 跳过。"""
    pkg_root = tmp_path / "accel-volume" / "packages"
    (pkg_root / "xcache_cuda" / "v0.3.12.post1").mkdir(parents=True)
    monkeypatch.setenv("ACCEL_VOLUME_PATH", str(tmp_path / "accel-volume"))

    # 命中 → 不抛
    script_builder._validate_accel_packages(["xcache_cuda:v0.3.12.post1"])

    # 版本漂移(镜像未含请求版本)→ 生成期 fail-fast,而非 install.py 运行期崩溃
    with pytest.raises(ValueError, match="does not contain package"):
        script_builder._validate_accel_packages(["xcache_cuda:v0.4.0"])

    # 工件目录不存在(测试/CI)→ 告警跳过,不阻断
    monkeypatch.setenv("ACCEL_VOLUME_PATH", str(tmp_path / "absent-volume"))
    script_builder._validate_accel_packages(["xcache_cuda:v0.3.12.post1"])
