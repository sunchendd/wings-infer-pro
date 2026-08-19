"""KV 存储后端(memcache / mooncake)端到端测试。

工具由 yaml 声明、按 ``kv_connector`` 内容路由(``AscendStoreConnector``);不再有 KV_STORE_BACKEND env。
name = 介质(cpu/disk/cpu_disk):后端工具(mooncake/memcache)是 **cpu 介质**下的内存卸载实现,
scheme 的 ``name`` 统一为 ``cpu``(工具由 connector + ``kv_connector_extra_config.backend`` 区分)。
覆盖 offload.py 的后端选择分支、render.py 的 ``{rank_ip}``/``{master_ip}`` 占位符与 ``{= expr}`` 算术求值、files 自描述落盘(path/content/scope/mode)、框架自动合成的 pre_serve/pre_serve_master
(mkdir / envsubst / master-only ``bash daemon &``,不监听端口),以及真实 YAML 资产
(MiniMax-M2.7-w8a8,mooncake 工具)+ backend 共享模板(kv_backends/<backend>/)的 resolve。
"""

from wings_accel.offload import smart_kv_offload_expander
from wings_accel.render import PlaceholderContext, render_pre_serve
from wings_accel.schemas import SmartKVCacheConfig


def make_ctx(**kw):
    base = dict(memory_capacity_gb=8)
    base.update(kw)
    return PlaceholderContext(**base)


def mooncake_block():
    """cpu 介质 scheme,mooncake 工具(AscendStoreConnector + backend:mooncake)。"""
    return [{
        "name": "cpu",
        "cli_params": {"kv_transfer_config": {
            "kv_connector": "AscendStoreConnector", "kv_role": "kv_both",
            "kv_load_failure_policy": "recompute",
            "kv_connector_extra_config": {"lookup_rpc_port": "1", "backend": "mooncake"},
        }},
        "envs": {"MOONCAKE_CONFIG_PATH": "/shared-volume/mooncake.json"},
        "files": [
            {"path": "mooncake.json", "scope": "all",
             "content": '{"local_hostname": "{rank_ip}", '
                        '"master_server_address": "{master_ip}:50088", '
                        '"global_segment_size": "{= memory_capacity_gb // gpu_count}GB"}'},
            {"path": "start_kv_serve.sh", "mode": "0755", "scope": "master",
             "content": "mooncake_master --port 50088\n"},
        ],
    }]


def memcache_block():
    """cpu 介质 scheme,memcache 工具(AscendStoreConnector + backend:memcache;纯内存)。"""
    return [{
        "name": "cpu",
        "cli_params": {"kv_transfer_config": {
            "kv_connector": "AscendStoreConnector", "kv_role": "kv_both",
            "kv_load_failure_policy": "recompute",
            "kv_connector_extra_config": {"lookup_rpc_port": "0", "backend": "memcache"},
        }},
        "envs": {"MMC_LOCAL_CONFIG_PATH": "/shared-volume/mmc_local.conf"},
        "files": [
            {"path": "mmc_local.conf", "scope": "all",
             "content": "meta = tcp://{master_ip}:15000\n"
                        "store = tcp://{rank_ip}:16000\n"
                        "world_size = 256\n"
                        "protocol = device_rdma\n"
                        "dram = {= memory_capacity_gb // gpu_count}GB\n"},
            {"path": "mmc_meta.conf", "scope": "master",
             "content": "meta = tcp://{master_ip}:15000\n"},
            {"path": "start_kv_serve.sh", "mode": "0755",
             "content": "MetaService\n"},
        ],
    }]


def lmcache_ascend_block():
    """ascend lmcache 单 scheme(LMCacheAscendConnectorV1Dynamic + module_path;方法三,纯 cpu/env,无 daemon)。

    name=cpu(cpu 介质,走三选一;不起独立服务,无 start_kv_serve.sh)。与原生 OffloadingConnector
    同为 cpu 介质的内嵌 connector,只是 connector 不同 + 带 kv_connector_module_path。
    """
    return [{
        "name": "cpu",
        "cli_params": {"kv_transfer_config": {
            "kv_connector": "LMCacheAscendConnectorV1Dynamic", "kv_role": "kv_both",
            "kv_connector_module_path": "lmcache_ascend.integration.vllm.lmcache_ascend_connector_v1",
        }},
        "envs": {"LMCACHE_LOCAL_CPU": "True", "LMCACHE_MAX_LOCAL_CPU_SIZE": "40",
                 "LMCACHE_EXTRA_CONFIG": '{"save_only_first_rank": false}'},
    }]


def test_lmcache_ascend_backend_routes_by_connector():
    """LMCacheAscendConnectorV1Dynamic(无 daemon)走三选一 cpu → 完整渲染 cli_params(connector+module_path)+ envs。

    daemon 判定(2026-08-06):无 start_kv_serve.sh → 走三选一按 name 选 cpu scheme。
    三选一 cpu 完整渲染 cli_params/envs/packages,与 backend 路径渲染能力一致(仅不起 daemon)。
    """
    ctx = make_ctx(memory_capacity_gb=8, gpu_count=4)
    cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=True, memory_offload_size_mode="8")
    out = smart_kv_offload_expander(cfg, lmcache_ascend_block(), ctx)
    assert out.scheme == "cpu"  # 三选一按 name=cpu 选(无 daemon 不走 backend)
    kt = out.engine_params.engine_config["kv_transfer_config"]
    assert kt["kv_connector"] == "LMCacheAscendConnectorV1Dynamic"
    assert kt["kv_connector_module_path"] == "lmcache_ascend.integration.vllm.lmcache_ascend_connector_v1"
    # envs 透传
    assert out.engine_params.env["LMCACHE_LOCAL_CPU"] == "True"
    assert out.engine_params.env["LMCACHE_MAX_LOCAL_CPU_SIZE"] == "40"
    # 无 daemon → 无 pre_serve / daemon
    assert out.pre_serve == [] and out.pre_serve_master == []


# ── 选择 + 框架自动 pre_serve ──


def test_mooncake_renders_and_synthesizes_pre_serve(monkeypatch, tmp_path):
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    ctx = make_ctx(memory_capacity_gb=8, gpu_count=4)
    cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=True, memory_offload_size_mode="8")
    out = smart_kv_offload_expander(cfg, mooncake_block(), ctx)
    assert out.scheme == "cpu"  # name=介质 cpu(mooncake 是工具,由 connector+backend 区分,不进 scheme 名)
    # {rank_ip}/{master_ip} → ${RANK_IP}/${MASTER_IP};{= memory_capacity_gb // gpu_count}GB → "2GB"(8//4)
    body = (tmp_path / "mooncake.json").read_text(encoding="utf-8")
    assert '"local_hostname": "${RANK_IP}"' in body
    assert '"master_server_address": "${MASTER_IP}:50088"' in body
    assert '"global_segment_size": "2GB"' in body
    # pre_serve(all):mkdir + export 默认 + envsubst 原地展开(runtime_vars=MASTER_IP,RANK_IP) + sed 兜底
    ps = "\n".join(out.pre_serve)
    assert "mkdir -p" in ps
    assert 'export MASTER_IP="${MASTER_IP:-127.0.0.1}" RANK_IP="${RANK_IP:-127.0.0.1}"' in ps
    # envsubst 主路径 + sed fallback(容器缺 gettext 时兜底,避免空 .tmp 覆盖原文件)
    assert "command -v envsubst" in ps and "envsubst '${MASTER_IP} ${RANK_IP}'" in ps
    assert "mooncake.json.tmp" in ps
    assert 'sed "s|\\${MASTER_IP}|$MASTER_IP|g;s|\\${RANK_IP}|$RANK_IP|g"' in ps
    # pre_serve_master:仅 master 后台起 daemon(脚本名 start_kv_serve.sh,不监听端口)
    psm = "\n".join(out.pre_serve_master)
    assert "bash " in psm and "start_kv_serve.sh &" in psm
    assert "/dev/tcp" not in psm


def test_client_scope_file_routes_to_pre_serve_client(monkeypatch, tmp_path):
    """scope=client 的文件:envsubst 进 pre_serve_client(仅非 master);all/master 桶不受影响。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    ctx = make_ctx(memory_capacity_gb=8, gpu_count=4)
    cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=True, memory_offload_size_mode="8")
    block = [{
        "name": "cpu",
        "cli_params": {"kv_transfer_config": {"kv_connector": "AscendStoreConnector",
            "kv_role": "kv_both",
            "kv_connector_extra_config": {"lookup_rpc_port": "1", "backend": "mooncake"}}},
        "envs": {},
        "files": [
            # 必须含 start_kv_serve.sh 才能走 backend 路径(daemon 判定);否则落三选一
            {"path": "start_kv_serve.sh", "mode": "0755", "scope": "master",
             "content": "mooncake_master --port 50088\n"},
            {"path": "worker_only.conf", "scope": "client",
             "content": "local_hostname = {rank_ip}\nmaster = {master_ip}\n"},
            {"path": "shared.conf", "scope": "all", "content": "ip = {rank_ip}\n"},
        ],
    }]
    out = smart_kv_offload_expander(cfg, block, ctx)
    # client 文件的 envsubst(runtime_vars=RANK_IP,MASTER_IP)进 pre_serve_client
    psc = "\n".join(out.pre_serve_client)
    assert "worker_only.conf" in psc and "envsubst" in psc
    # all 文件进 pre_serve;client 文件不进 pre_serve / pre_serve_master
    assert "shared.conf" in "\n".join(out.pre_serve)
    assert "worker_only.conf" not in "\n".join(out.pre_serve)
    assert "worker_only.conf" not in "\n".join(out.pre_serve_master)


def test_memcache_renders_protocol_dram(monkeypatch, tmp_path):
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    ctx = make_ctx(memory_capacity_gb=8, gpu_count=4)
    cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=True, memory_offload_size_mode="8")
    out = smart_kv_offload_expander(cfg, memcache_block(), ctx)
    assert out.scheme == "cpu"  # name=介质 cpu(memcache 是工具,由 connector+backend 区分)
    # mmc_local.conf(scope=all):world_size 字面量、protocol 字面量、dram per-card GB、master ${MASTER_IP}
    local = (tmp_path / "mmc_local.conf").read_text(encoding="utf-8")
    assert "world_size = 256" in local          # 字面量,不经占位符
    assert "protocol = device_rdma" in local
    assert "dram = 2GB" in local                # {= memory_capacity_gb // gpu_count}GB → "<per_card>GB"(8GB//4 卡)
    assert "meta = tcp://${MASTER_IP}:15000" in local
    assert "store = tcp://${RANK_IP}:16000" in local
    # pre_serve(all)envsubst mmc_local.conf(含 {master_ip}+{rank_ip});pre_serve_master envsubst mmc_meta.conf + 起 MetaService
    assert "envsubst '${MASTER_IP} ${RANK_IP}'" in "\n".join(out.pre_serve)
    psm = "\n".join(out.pre_serve_master)
    assert "envsubst" in psm and "mmc_meta.conf" in psm
    assert "bash " in psm and "start_kv_serve.sh &" in psm
    assert "/dev/tcp" not in psm


def test_backend_missing_falls_back_to_cpu():
    # yaml 只声明 cpu(无后端 scheme)→ 走 native cpu 路径
    ctx = make_ctx(memory_offload_enabled=True, memory_capacity_gb=64)
    cfg = SmartKVCacheConfig(
        enabled=True, memory_offload_enabled=True, memory_offload_size_mode="64",
    )
    block = [{
        "name": "cpu",
        "cli_params": {"kv_transfer_config": {"kv_connector": "OffloadingConnector",
         "kv_role": "kv_both", "kv_connector_extra_config": {"cpu_bytes_to_use": "{mem_gb_to_bytes}"}}},
        "envs": {},
    }]
    out = smart_kv_offload_expander(cfg, block, ctx)
    assert out.scheme == "cpu"
    assert out.pre_serve == [] and out.pre_serve_master == []


def test_memory_offload_disabled_skips_backend():
    # memory_offload 未启用 → 即便声明了后端 scheme 也不产出(工具由 env 开关 + yaml 共同决定)
    ctx = make_ctx()
    cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=False)
    assert smart_kv_offload_expander(cfg, mooncake_block(), ctx) is None


def test_disabled_returns_none():
    ctx = make_ctx()
    cfg = SmartKVCacheConfig(enabled=False, memory_offload_enabled=True)
    assert smart_kv_offload_expander(cfg, mooncake_block(), ctx) is None


# ── render_pre_serve 占位符 / 拓扑占位保留(逃生口仍可用)──


def test_render_pre_serve_preserves_topology_placeholders():
    ctx = make_ctx()
    cmds = ["echo $local_ip ${RANK_IP:-127.0.0.1}"]
    out = render_pre_serve(cmds, ctx)
    assert out == ["echo $local_ip ${RANK_IP:-127.0.0.1}"]  # $local_ip / ${VAR} 原样保留


def test_render_pre_serve_empty():
    assert render_pre_serve(None, make_ctx()) == []
    assert render_pre_serve([], make_ctx()) == []


# ── 真实 YAML 资产(MiniMax-M2.7-w8a8 mooncake)端到端 ──


def test_real_yaml_mooncake_end_to_end(monkeypatch, tmp_path):
    from wings_accel import LoadFlags, resolve_smart_accel_from_config

    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    out = resolve_smart_accel_from_config(
        config_root="src/wings_accel",
        engine="vllm-ascend", engine_version="0.21.0rc",
        hardware_family="ascend-a2", model_name="MiniMax-M2.7-w8a8-QuaRot",
        flags=LoadFlags(kv=True, memory_offload_size_mode="8"),
        gpu_count=8,
    )
    assert out is not None
    assert out.smart_kv_cache_scheme == "cpu"  # name=介质 cpu(MiniMax 用 mooncake 工具,scheme 名即介质)
    # mooncake.json 落盘 + 占位符填实:
    #   {= memory_capacity_gb // gpu_count}GB → "1GB"(8GB//8 卡);{rank_ip}/{master_ip} → ${RANK_IP}/${MASTER_IP}
    body = (tmp_path / "mooncake.json").read_text(encoding="utf-8")
    assert '"global_segment_size": "1GB"' in body
    assert '"local_hostname": "${RANK_IP}"' in body
    assert '"master_server_address": "${MASTER_IP}:50088"' in body
    # mooncake 需 LD_LIBRARY_PATH 加载 ascend_transport.so
    assert "/usr/local/lib" in out.engine_params.env.get("LD_LIBRARY_PATH", "")
    # 框架自动 pre_serve:envsubst + daemon(master-only bash,不监听端口)
    assert "envsubst" in "\n".join(out.pre_serve)
    psm = "\n".join(out.pre_serve_master)
    assert "start_kv_serve.sh &" in psm
    assert "/dev/tcp" not in psm
    # engine_config 含 kv_transfer_config(backend:mooncake)
    ktc = out.engine_params.engine_config["kv_transfer_config"]
    assert ktc["kv_connector"] == "AscendStoreConnector"
    assert ktc["kv_connector_extra_config"]["backend"] == "mooncake"
    assert out.engine_params.env["MOONCAKE_CONFIG_PATH"] == "/shared-volume/mooncake.json"


def test_real_yaml_mooncake_auto_derives_capacity(monkeypatch, tmp_path):
    """后端 scheme + KV_MEM_OFFLOAD_SIZE=auto:容量经 pod 内存估算派生,不再静默=0/留字面占位符。

    has_memory_method 含后端 scheme(按 connector 判定)→ memory_on=True → auto 估算跑 → 真实 GB 值。
    """
    import re
    from wings_accel import LoadFlags, resolve_smart_accel_from_config

    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    out = resolve_smart_accel_from_config(
        config_root="src/wings_accel",
        engine="vllm-ascend", engine_version="0.21.0rc",
        hardware_family="ascend-a2", model_name="MiniMax-M2.7-w8a8-QuaRot",
        flags=LoadFlags(kv=True, memory_offload_size_mode="auto",
                        pod_available_memory_gb=200, min_offload_threshold_gb=50),
        gpu_count=8,
    )
    assert out is not None
    body = (tmp_path / "mooncake.json").read_text(encoding="utf-8")
    # {= expr} 解析为真实 "<n>GB"(估算后按 8 卡均分),不留字面 {= ...}
    assert '"global_segment_size": "{= memory_capacity_gb // gpu_count}GB"' not in body
    m = re.search(r'"global_segment_size":\s*"(\d+)GB"', body)
    assert m and int(m.group(1)) >= 1


# ── 真实 YAML 资产(DeepSeek-V4-Flash lmcache-ascend)端到端 ──


def test_real_yaml_deepseek_v4flash_lmcache_packages(monkeypatch, tmp_path):
    """DeepSeek-V4-Flash 的 LMCache cpu scheme 声明 lmcache-ascend 依赖 → packages 进 out。

    kv_connector=LMCacheAscendConnectorV1Dynamic(非 AscendStoreConnector backend)→ 走
    cpu 三选一路径,packages = extract_packages(cpu scheme) = ["lmcache-ascend:v0.4.5"],
    供 install 段 ``--config`` 拼依赖。
    """
    from wings_accel import LoadFlags, resolve_smart_accel_from_config

    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    out = resolve_smart_accel_from_config(
        config_root="src/wings_accel",
        engine="vllm-ascend", engine_version="0.21.0rc",
        hardware_family="ascend-a2", model_name="DeepSeek-V4-Flash-w8a8-mtp",
        flags=LoadFlags(kv=True, memory_offload_size_mode="8"),
        gpu_count=1,
    )
    assert out is not None
    assert out.smart_kv_cache_scheme == "cpu"  # name=介质 cpu(LMCacheAscendConnectorV1Dynamic 工具)
    # lmcache-ascend 依赖透传进 out.packages(name:version,供 install 段 --config)
    assert out.packages == ["lmcache-ascend:v0.4.5"]
    # engine_config 仍是 LMCacheAscend 连接器(非 mooncake/AscendStore)
    ktc = out.engine_params.engine_config["kv_transfer_config"]
    assert ktc["kv_connector"] == "LMCacheAscendConnectorV1Dynamic"
    # LMCache 环境变量注入
    env = out.engine_params.env
    assert env["LMCACHE_LOCAL_CPU"] == "True"
    assert env["LMCACHE_MAX_LOCAL_CPU_SIZE"] == "8"


def test_real_yaml_deepseek_v4flash_lmcache_packages_a3(monkeypatch, tmp_path):
    """规则同 ascend-a2,但落在 A3 资产(engine_variant→hardware_family 必须存在同版本/硬件的资产)。"""
    from wings_accel import LoadFlags, resolve_smart_accel_from_config

    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    out = resolve_smart_accel_from_config(
        config_root="src/wings_accel",
        engine="vllm-ascend", engine_version="0.21.0rc",
        hardware_family="ascend-a3", model_name="DeepSeek-V4-Flash-w8a8-mtp",
        flags=LoadFlags(kv=True, memory_offload_size_mode="8"),
        gpu_count=1,
    )
    assert out is not None
    assert out.packages == ["lmcache-ascend:v0.4.5"]
