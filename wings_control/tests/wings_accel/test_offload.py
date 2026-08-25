from wings_accel.offload import smart_kv_offload_expander
from wings_accel.render import PlaceholderContext, _fill_str
from wings_accel.schemas import SmartKVCacheConfig


def make_ctx(**kw):
    base = dict(memory_capacity_gb=64, disk_capacity_gb=200, disk_path="/mnt/kv")
    base.update(kw)
    return PlaceholderContext(**base)


def _lmcache_files(cpu=False):
    """disk/cpu_disk scheme 的 files 块:lmcache_config.yaml(占位符由 ctx 后续填充)。

    NOTE:``{disk_path}`` / ``{qat_*}`` 是留给 ``fill_placeholders`` 的字面量占位符,
    不是 format 参数。

    Args:
        cpu: True → cpu_disk 形态(多 local_cpu + max_local_cpu_size 两行)。

    Returns:
        ``[{"name": "lmcache_config.yaml", "content": <yaml text>}]``。
    """
    cpu_body = (
        "local_cpu: true\n"
        "max_local_cpu_size: {memory_capacity_gb}\n"
    ) if cpu else ""
    content = (
        "chunk_size: 256\n"
        + cpu_body +
        "local_disk: {disk_path}\n"
        "max_local_disk_size: {disk_capacity_gb}\n"
        "extra_config:\n"
        "  wings:\n"
        "    qat:\n"
        "      enabled: {qat_enabled}\n"
        "      module_name: kv_agent\n"
        "      instance_num: {qat_device_count}\n"
        "      loss_level: {qat_compression_level}\n"
        "      log_enabled: 1\n"
    )
    return [{"name": "lmcache_config.yaml", "content": content}]


def make_block():
    """三 scheme(cpu/disk/cpu_disk),各最多一项。"""
    return [
        {  # cpu:纯原生 OffloadingConnector,无 lmcache 包 / 无 lmcache_config
            "name": "cpu",
            "cli_params": {
                "kv_transfer_config": {
                    "kv_connector": "OffloadingConnector",
                    "kv_role": "kv_both",
                    "kv_connector_extra_config": {"num_cpu_blocks": "{mem_gb_to_blocks}"},
                }
            },
            "envs": {},
        },
        {  # disk:lmcache,disk-only
            "name": "disk",
            "packages": {"lmcache": "v0.3.15"},
            "cli_params": {
                "kv_transfer_config": {
                    "kv_connector": "LMCacheConnectorV1",
                    "kv_role": "kv_both",
                    "kv_connector_extra_config": {
                        "local_disk": "{disk_path}",
                        "max_local_disk_size": "{disk_capacity_gb}",
                    },
                }
            },
            "envs": {
                "LMCACHE_CONFIG_FILE": "/shared-volume/lmcache_config.yaml",
                "LMCACHE_LOCAL_DISK": "{disk_path}",
                "LMCACHE_MAX_LOCAL_DISK_SIZE": "{disk_capacity_gb}",
            },
            "files": _lmcache_files(cpu=False),
        },
        {  # cpu_disk:lmcache,cpu+disk(比 disk 多 local_cpu + max_local_cpu_size)
            "name": "cpu_disk",
            "packages": {"lmcache": "v0.3.15"},
            "cli_params": {
                "kv_transfer_config": {
                    "kv_connector": "LMCacheConnectorV1",
                    "kv_role": "kv_both",
                    "kv_connector_extra_config": {
                        "local_cpu": True,
                        "max_local_cpu_size": "{memory_capacity_gb}",
                        "local_disk": "{disk_path}",
                        "max_local_disk_size": "{disk_capacity_gb}",
                    },
                }
            },
            "envs": {
                "LMCACHE_CONFIG_FILE": "/shared-volume/lmcache_config.yaml",
                "LMCACHE_LOCAL_CPU": "true",
                "LMCACHE_MAX_LOCAL_CPU_SIZE": "{memory_capacity_gb}",
                "LMCACHE_LOCAL_DISK": "{disk_path}",
                "LMCACHE_MAX_LOCAL_DISK_SIZE": "{disk_capacity_gb}",
            },
            "files": _lmcache_files(cpu=True),
        },
    ]


# ── 三选一 ──────────────────────────────────────────────────────────────────

def test_offload_disabled():
    """主开关关 → None。"""
    cfg = SmartKVCacheConfig(enabled=False)
    assert smart_kv_offload_expander(cfg, None, make_ctx()) is None


def test_offload_cpu_only():
    """(mem, disk)=(T,F) → cpu(原生 OffloadingConnector);无 lmcache env / 无包。"""
    cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=True, memory_offload_size_mode="64")
    ctx = make_ctx(memory_offload_enabled=True)
    out = smart_kv_offload_expander(cfg, make_block(), ctx)
    assert out.scheme == "cpu"
    cfg_out = out.engine_params.engine_config
    assert cfg_out["kv_transfer_config"]["kv_connector_extra_config"]["num_cpu_blocks"] == "4096"
    assert out.engine_params.env == {}       # cpu 不注入任何 LMCACHE_*
    assert out.packages == []                 # cpu 原生,无 lmcache 包


def test_offload_disk_only(monkeypatch, tmp_path):
    """(mem, disk)=(F,T) → disk(lmcache);带 lmcache 包 + LMCACHE_LOCAL_DISK + lmcache_config.yaml。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))  # 写盘落临时目录,不依赖真实 /shared-volume
    cfg = SmartKVCacheConfig(
        enabled=True, disk_offload_enabled=True, disk_capacity_gb=200, disk_path="/mnt/kv",
    )
    ctx = make_ctx(disk_offload_enabled=True)
    out = smart_kv_offload_expander(cfg, make_block(), ctx)
    assert out.scheme == "disk"
    assert out.packages == ["lmcache:v0.3.15"]
    cfg_out = out.engine_params.engine_config
    assert cfg_out["kv_transfer_config"]["kv_connector"] == "LMCacheConnectorV1"
    assert out.engine_params.env["LMCACHE_LOCAL_DISK"] == "/mnt/kv"
    assert out.engine_params.env["LMCACHE_CONFIG_FILE"] == "/shared-volume/lmcache_config.yaml"
    assert out.engine_params.env["LMCACHE_QAT_ENABLED"] == "False"   # qat 未开 → False


def test_offload_cpu_disk(monkeypatch, tmp_path):
    """(mem, disk)=(T,T) → cpu_disk(lmcache 同时管 cpu+disk);local_cpu + 内存大小给到。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))  # 写盘落临时目录,不依赖真实 /shared-volume
    cfg = SmartKVCacheConfig(
        enabled=True, memory_offload_enabled=True, memory_offload_size_mode="40",
        disk_offload_enabled=True, disk_capacity_gb=200, disk_path="/mnt/kv",
    )
    ctx = make_ctx(memory_offload_enabled=True, disk_offload_enabled=True, memory_capacity_gb=40)
    out = smart_kv_offload_expander(cfg, make_block(), ctx)
    assert out.scheme == "cpu_disk"
    assert out.packages == ["lmcache:v0.3.15"]
    cfg_out = out.engine_params.engine_config
    extra = cfg_out["kv_transfer_config"]["kv_connector_extra_config"]
    assert extra["local_cpu"] is True
    assert extra["max_local_cpu_size"] == "40"
    assert extra["local_disk"] == "/mnt/kv"
    assert out.engine_params.env["LMCACHE_MAX_LOCAL_CPU_SIZE"] == "40"
    assert out.engine_params.env["LMCACHE_MAX_LOCAL_DISK_SIZE"] == "200"


# ── fallback(cpu_disk 缺 → disk > cpu > None)────────────────────────────────

def test_offload_cpu_disk_fallback_to_disk(monkeypatch, tmp_path):
    """cpu_disk 缺失但 disk 在 → 退化 disk(优先)。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))  # 写盘落临时目录,不依赖真实 /shared-volume
    block = [s for s in make_block() if s["name"] != "cpu_disk"]
    cfg = SmartKVCacheConfig(
        enabled=True, memory_offload_enabled=True, memory_offload_size_mode="40",
        disk_offload_enabled=True, disk_capacity_gb=200, disk_path="/mnt/kv",
    )
    ctx = make_ctx(memory_offload_enabled=True, disk_offload_enabled=True, memory_capacity_gb=40)
    out = smart_kv_offload_expander(cfg, block, ctx)
    assert out.scheme == "disk"


def test_offload_cpu_disk_fallback_to_cpu():
    """cpu_disk + disk 都缺,仅 cpu 在 → 退化 cpu。"""
    block = [{"name": "cpu", "cli_params": {}, "envs": {}}]
    cfg = SmartKVCacheConfig(
        enabled=True, memory_offload_enabled=True, memory_offload_size_mode="40",
        disk_offload_enabled=True, disk_capacity_gb=200, disk_path="/mnt/kv",
    )
    ctx = make_ctx(memory_offload_enabled=True, disk_offload_enabled=True, memory_capacity_gb=40)
    out = smart_kv_offload_expander(cfg, block, ctx)
    assert out.scheme == "cpu"


def test_offload_cpu_disk_all_missing_returns_none():
    """cpu_disk 缺,disk/cpu 也都缺 → 关闭(None)。"""
    block = [{"name": "other", "cli_params": {}, "envs": {}}]
    cfg = SmartKVCacheConfig(
        enabled=True, memory_offload_enabled=True, memory_offload_size_mode="40",
        disk_offload_enabled=True,
    )
    ctx = make_ctx(memory_offload_enabled=True, disk_offload_enabled=True)
    assert smart_kv_offload_expander(cfg, block, ctx) is None


# ── lmcache_config.yaml + QAT ───────────────────────────────────────────────

def test_offload_qat_plans_lmcache_yaml_without_writing(monkeypatch, tmp_path):
    """disk 命中 + qat 开 → 返回 lmcache 文件计划且不写盘。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    cfg = SmartKVCacheConfig(
        enabled=True, disk_offload_enabled=True, disk_capacity_gb=200, disk_path="/mnt/kv",
        qat_enabled=True, qat_device_count=4, qat_compression_level=2,
    )
    ctx = make_ctx(
        disk_offload_enabled=True, qat_enabled=True, qat_device_count=4, qat_compression_level=2,
    )
    out = smart_kv_offload_expander(cfg, make_block(), ctx, engine_name="vllm")
    assert out.engine_params.env["LMCACHE_CONFIG_FILE"] == "/shared-volume/lmcache_config.yaml"
    assert out.engine_params.env["LMCACHE_QAT_ENABLED"] == "True"
    assert [item.path for item in out.generated_files] == [
        str(tmp_path / "lmcache_config.yaml")
    ]
    content = out.generated_files[0].content
    # 容量段 + qat 段都渲染(qat 字段原生类型,无引号)
    assert "chunk_size: 256" in content
    assert "local_disk: /mnt/kv" in content
    assert "extra_config:" in content and "wings:" in content
    assert "enabled: true" in content
    assert "instance_num: 4" in content
    assert "loss_level: 2" in content
    # qat 走 lmcache_config.yaml + env,不泄漏进 kv_transfer_config
    extra = out.engine_params.engine_config["kv_transfer_config"]["kv_connector_extra_config"]
    assert "qat" not in extra
    assert not (tmp_path / "lmcache_config.yaml").exists()


def test_offload_qat_off_still_plans_yaml(monkeypatch, tmp_path):
    """disk 命中但 qat 关 → 返回 qat 关闭的 lmcache 文件计划。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    cfg = SmartKVCacheConfig(
        enabled=True, disk_offload_enabled=True, disk_capacity_gb=200, disk_path="/mnt/kv",
    )
    ctx = make_ctx(disk_offload_enabled=True)
    out = smart_kv_offload_expander(cfg, make_block(), ctx, engine_name="vllm")
    assert out.engine_params.env["LMCACHE_QAT_ENABLED"] == "False"
    assert out.engine_params.env["LMCACHE_CONFIG_FILE"] == "/shared-volume/lmcache_config.yaml"
    content = out.generated_files[0].content
    assert "enabled: false" in content
    assert not (tmp_path / "lmcache_config.yaml").exists()


def test_offload_skipped_without_lmcache_template(monkeypatch, tmp_path):
    """disk 命中但 scheme 缺 files 块 → 不写盘 / 不注入 LMCACHE_QAT_ENABLED。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    block = [
        {"name": "disk",
         "cli_params": {"kv_transfer_config": {"kv_connector": "LMCacheConnectorV1", "kv_role": "kv_both"}},
         "envs": {}},
    ]
    cfg = SmartKVCacheConfig(
        enabled=True, disk_offload_enabled=True, disk_capacity_gb=200, disk_path="/mnt/kv",
        qat_enabled=True, qat_device_count=4, qat_compression_level=2,
    )
    ctx = make_ctx(
        disk_offload_enabled=True, qat_enabled=True, qat_device_count=4, qat_compression_level=2,
    )
    out = smart_kv_offload_expander(cfg, block, ctx, engine_name="vllm")
    assert "LMCACHE_QAT_ENABLED" not in out.engine_params.env
    assert "LMCACHE_CONFIG_FILE" not in out.engine_params.env
    assert not (tmp_path / "lmcache_config.yaml").exists()


def test_offload_qat_disabled_for_non_vllm(monkeypatch, tmp_path):
    """非 vllm disk 命中 → qat 关闭的 lmcache 文件计划。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    cfg = SmartKVCacheConfig(
        enabled=True, disk_offload_enabled=True, disk_capacity_gb=200, disk_path="/mnt/kv",
        qat_enabled=True, qat_device_count=4, qat_compression_level=2,
    )
    out = smart_kv_offload_expander(
        cfg, make_block(), make_ctx(disk_offload_enabled=True), engine_name="vllm-ascend",
    )
    assert out.engine_params.env["LMCACHE_QAT_ENABLED"] == "False"
    content = out.generated_files[0].content
    assert "enabled: false" in content
    assert not (tmp_path / "lmcache_config.yaml").exists()


def test_offload_no_lmcache_for_cpu_scheme(monkeypatch, tmp_path):
    """cpu 命中(纯内存,非 disk)→ 不写 lmcache_config.yaml / 不注入 LMCACHE_*。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    cfg = SmartKVCacheConfig(
        enabled=True, memory_offload_enabled=True, memory_offload_size_mode="64",
        qat_enabled=True, qat_device_count=4, qat_compression_level=2,
    )
    out = smart_kv_offload_expander(
        cfg, make_block(), make_ctx(memory_offload_enabled=True), engine_name="vllm",
    )
    assert "LMCACHE_QAT_ENABLED" not in out.engine_params.env
    assert "LMCACHE_CONFIG_FILE" not in out.engine_params.env
    assert not (tmp_path / "lmcache_config.yaml").exists()


# ── 其它回归 ────────────────────────────────────────────────────────────────

def test_offload_no_matching_media():
    """主开关开但目标 scheme 无对应方案 → None(cpu 请求,yaml 只有 disk)。"""
    cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=True, memory_offload_size_mode="64")
    block = [{"name": "disk", "cli_params": {}}]
    assert smart_kv_offload_expander(cfg, block, make_ctx(memory_offload_enabled=True)) is None


def test_offload_missing_block_fallback():
    """block 为 None → None。"""
    cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=True, memory_offload_size_mode="64")
    assert smart_kv_offload_expander(cfg, None, make_ctx()) is None


def test_offload_no_media_enabled():
    """mem/disk 都没开 → None。"""
    cfg = SmartKVCacheConfig(enabled=True, memory_offload_enabled=False, disk_offload_enabled=False)
    assert smart_kv_offload_expander(cfg, make_block(), make_ctx()) is None


def test_swap_space_zero_when_memory_on():
    """M_swap=0:memory_on 时 {cpu_swap_space_gb} → '0'。"""
    assert _fill_str("{cpu_swap_space_gb}", make_ctx(memory_offload_enabled=True)) == "0"


def test_swap_space_literal_when_memory_off():
    """memory_off 时 {cpu_swap_space_gb} 原样返回字面占位符。"""
    assert _fill_str("{cpu_swap_space_gb}", make_ctx(memory_offload_enabled=False)) == "{cpu_swap_space_gb}"
