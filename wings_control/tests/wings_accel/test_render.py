"""render 渲染层单测 — cli_params → 结构化 engine_config + 占位符 + 合并。"""

from wings_accel.render import (
    PlaceholderContext,
    deep_merge_dicts,
    fill_envs,
    merge_engine_params,
    render_engine_config,
    write_scheme_files,
)
from wings_accel.schemas import EngineParams


def ctx(**kw):
    return PlaceholderContext(**kw)


def test_values_keep_structure():
    data = {
        "trust_remote_code": True,
        "kv_cache_dtype": "fp8",
        "max_num_seqs": 8,
        "hf_overrides": {"enable_index_cache": True, "indexcache_freq": 4},
        "prompt": ["a", "b"],
    }
    assert render_engine_config(data, ctx()) == data


def test_placeholder_mem_gb_to_blocks():
    c = ctx(memory_offload_enabled=True, memory_capacity_gb=64)
    out = render_engine_config({"kv_transfer_config": {"num_cpu_blocks": "{mem_gb_to_blocks}"}}, c)
    assert out == {"kv_transfer_config": {"num_cpu_blocks": "4096"}}


def test_placeholder_mem_gb_to_blocks_zero_when_disabled():
    c = ctx(memory_offload_enabled=False, memory_capacity_gb=64)
    assert render_engine_config({"x": "{mem_gb_to_blocks}"}, c) == {"x": "0"}


def test_placeholder_mem_gb_to_bytes():
    """CUDA(原生 vLLM ≥v0.14)cpu_bytes_to_use:GiB → 字节。64 GiB = 68719476736 字节。"""
    c = ctx(memory_offload_enabled=True, memory_capacity_gb=64)
    out = render_engine_config(
        {"kv_transfer_config": {"kv_connector_extra_config": {"cpu_bytes_to_use": "{mem_gb_to_bytes}"}}},
        c,
    )
    assert out == {
        "kv_transfer_config": {"kv_connector_extra_config": {"cpu_bytes_to_use": "68719476736"}}
    }


def test_placeholder_mem_gb_to_bytes_zero_when_disabled():
    """memory_offload 关闭 → {mem_gb_to_bytes} → '0'(与 blocks 占位一致)。"""
    c = ctx(memory_offload_enabled=False, memory_capacity_gb=64)
    assert render_engine_config({"x": "{mem_gb_to_bytes}"}, c) == {"x": "0"}


def test_placeholder_path_token():
    c = ctx(draft_model_path="/draft/m")
    out = render_engine_config({"speculative_config": {"method": "eagle3", "model": "$path"}}, c)
    assert out == {"speculative_config": {"method": "eagle3", "model": "/draft/m"}}


def test_fill_envs():
    c = ctx(memory_offload_enabled=True, memory_capacity_gb=40)
    assert fill_envs({"LMCACHE_MAX_LOCAL_CPU_SIZE": "{memory_capacity_gb}"}, c) == {
        "LMCACHE_MAX_LOCAL_CPU_SIZE": "40"
    }


def test_deep_merge_dicts_nested():
    base = {"kv_transfer_config": {"a": 1}}
    deep_merge_dicts(base, {"kv_transfer_config": {"b": 2}, "x": 9})
    assert base == {"kv_transfer_config": {"a": 1, "b": 2}, "x": 9}


def test_merge_engine_params():
    a = EngineParams(env={"A": "1"}, engine_config={"a": 1, "same": "old"})
    b = EngineParams(env={"A": "2", "B": "3"}, engine_config={"b": 2, "same": "new"})
    m = merge_engine_params(a, b)
    assert m.env == {"A": "2", "B": "3"}
    assert m.engine_config == {"a": 1, "same": "new", "b": 2}
    assert a.env == {"A": "1"}


# ── 通用 files: 写文件(write_scheme_files)──────────────────────────────────


def test_write_scheme_files_renders_multiple_formats(monkeypatch, tmp_path):
    """验证多文件(JSON + .conf)落盘:占位符子串填充正确 + 返回已写路径(保持输入顺序)。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    c = ctx(
        disk_offload_enabled=True, disk_path="/mnt/kv",
        qat_enabled=True, qat_device_count=4, qat_compression_level=2,
    )
    files = [
        {"name": "mooncake.json",
         "content": '{"local_disk": "{disk_path}", "instance_num": {qat_device_count}}\n'},
        {"name": "mmc_local.conf",
         "content": "ock.mmc.local_service.dram.size = 10GB\nlocal_disk = {disk_path}\n"},
    ]
    written = write_scheme_files(files, c)
    # 返回路径 = SHARED_VOLUME_PATH/<name>,顺序与输入一致
    assert written == [str(tmp_path / "mooncake.json"), str(tmp_path / "mmc_local.conf")]
    # 占位符子串全部填实(多行文本里的 {占位符} 整体替换)
    assert (tmp_path / "mooncake.json").read_text(encoding="utf-8") == (
        '{"local_disk": "/mnt/kv", "instance_num": 4}\n'
    )
    assert (tmp_path / "mmc_local.conf").read_text(encoding="utf-8") == (
        "ock.mmc.local_service.dram.size = 10GB\nlocal_disk = /mnt/kv\n"
    )


def test_write_scheme_files_empty_no_write(monkeypatch, tmp_path):
    """验证 files=None / 空列表 → 返回 [],且不创建目录、不写盘(早退)。"""
    target = tmp_path / "shared"  # 不应被创建
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(target))
    assert not write_scheme_files(None, ctx())
    assert not write_scheme_files([], ctx())
    assert not target.exists()  # 早退,未 mkdir


def test_write_scheme_files_explicit_volume_overrides_env(monkeypatch, tmp_path):
    """验证显式 volume 参数覆盖 SHARED_VOLUME_PATH 环境变量。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", "/should-not-be-used")
    target = tmp_path / "out"
    written = write_scheme_files(
        [{"name": "a.txt", "content": "enabled: {qat_enabled}\n"}],
        ctx(qat_enabled=True),
        volume=str(target),
    )
    assert written == [str(target / "a.txt")]
    assert (target / "a.txt").read_text(encoding="utf-8") == "enabled: true\n"


def test_write_scheme_files_unresolved_token_kept_literal(monkeypatch, tmp_path):
    """验证条件未满足的占位符(disk 未启用时的 {disk_path})原样保留字面量。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    write_scheme_files([{"name": "c.yaml", "content": "local_disk: {disk_path}\n"}], ctx())
    # disk_offload_enabled=False → {disk_path} 不解析,保留字面量
    assert (tmp_path / "c.yaml").read_text(encoding="utf-8") == "local_disk: {disk_path}\n"
