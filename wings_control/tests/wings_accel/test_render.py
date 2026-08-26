"""render 渲染层单测 — cli_params → 结构化 engine_config + 占位符 + 合并。"""

import pytest

from wings_accel.render import (
    PlaceholderContext,
    deep_merge_dicts,
    extract_packages,
    fill_envs,
    merge_engine_params,
    plan_scheme_files,
    render_engine_config,
)
from wings_accel.schemas import (
    EngineParams,
    GeneratedFile,
    SmartAccelConfigurationError,
    SmartAccelPackageFormatError,
)


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


@pytest.mark.parametrize("packages", [
    ["Demo_Pkg:1.2.3"],
    "Demo_Pkg:1.2.3",
])
def test_extract_packages_supports_legacy_string_formats(packages):
    """旧列表和单字符串写法必须进入依赖输出,且保留原始声明(规范化值仅用于冲突比较)。"""
    assert extract_packages({"packages": packages}) == ["Demo_Pkg:1.2.3"]


@pytest.mark.parametrize("packages", [
    "lmcache",       # 裸包名:缺 version
    ["lmcache"],     # list 内裸包名
    42,              # 顶层非法类型:int
    [42],            # list 内非法类型:int
])
def test_extract_packages_rejects_invalid_formats(packages):
    """非法 packages 形态必须抛 SmartAccelPackageFormatError,不得静默变空依赖。"""
    with pytest.raises(SmartAccelPackageFormatError):
        extract_packages({"packages": packages})


# ── 通用 files: 计划文件(plan_scheme_files) ─────────────────────────────────


def test_plan_scheme_files_renders_multiple_formats_without_writing(monkeypatch, tmp_path):
    """验证多文件渲染为计划,并且不创建目录或文件。"""
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
    planned = plan_scheme_files(files, c)
    assert [item.path for item in planned] == [
        str(tmp_path / "mooncake.json"), str(tmp_path / "mmc_local.conf")
    ]
    assert all(item.runtime_vars == [] for item in planned)
    assert planned[0] == GeneratedFile(
        path=str(tmp_path / "mooncake.json"),
        content=(
        '{"local_disk": "/mnt/kv", "instance_num": 4}\n'
        ),
    )
    assert planned[1].content == "ock.mmc.local_service.dram.size = 10GB\nlocal_disk = /mnt/kv\n"
    assert not (tmp_path / "mooncake.json").exists()
    assert not (tmp_path / "mmc_local.conf").exists()


def test_plan_scheme_files_empty_does_not_create_a_directory(monkeypatch, tmp_path):
    """验证 files=None / 空列表 → 返回 [],且不创建目录。"""
    target = tmp_path / "shared"  # 不应被创建
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(target))
    assert not plan_scheme_files(None, ctx())
    assert not plan_scheme_files([], ctx())
    assert not target.exists()


def test_plan_scheme_files_explicit_volume_overrides_env(monkeypatch, tmp_path):
    """验证显式 volume 参数覆盖 SHARED_VOLUME_PATH,并且不写盘。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", "/should-not-be-used")
    target = tmp_path / "out"
    planned = plan_scheme_files(
        [{"name": "a.txt", "content": "enabled: {qat_enabled}\n"}],
        ctx(qat_enabled=True),
        volume=str(target),
    )
    assert [item.path for item in planned] == [str(target / "a.txt")]
    assert planned[0].content == "enabled: true\n"
    assert not target.exists()


def test_plan_scheme_files_unresolved_token_kept_literal(monkeypatch, tmp_path):
    """验证条件未满足的占位符仍保留在文件计划内容中。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    planned = plan_scheme_files(
        [{"name": "c.yaml", "content": "local_disk: {disk_path}\n"}], ctx()
    )
    assert planned[0].content == "local_disk: {disk_path}\n"
    assert not (tmp_path / "c.yaml").exists()



def test_plan_scheme_files_preserves_source_metadata(monkeypatch, tmp_path):
    """文件计划必须保留实际 YAML 文件和 files[] 来源路径，供 audit 追溯。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    planned = plan_scheme_files(
        [{"name": "config.json", "content": "{}\n"}],
        ctx(
            source_file="/config/smart-accel/model.yaml",
            source_path="smart_accel.standalone.strategies.single_node.kv_offload[0]",
        ),
        source_path_prefix="smart_accel.standalone.strategies.single_node.kv_offload[0]",
    )
    assert planned[0].source_file == "/config/smart-accel/model.yaml"
    assert planned[0].source_path == (
        "smart_accel.standalone.strategies.single_node.kv_offload[0].files[0]"
    )


def test_plan_scheme_files_reads_src_only_from_config_root(tmp_path):
    """验证 files.src 只能读取当前 SmartAccel 资产根内的相对文件。"""
    asset_root = tmp_path / "smart-accel"
    asset_root.mkdir()
    (asset_root / "template.conf").write_text("enabled = true\n", encoding="utf-8")

    planned = plan_scheme_files(
        [{"name": "target.conf", "src": "template.conf"}],
        ctx(config_root=str(asset_root)),
    )

    assert planned[0].content == "enabled = true\n"


@pytest.mark.parametrize("src", ["../outside.conf", "/tmp/outside.conf", "missing.conf"])
def test_plan_scheme_files_rejects_invalid_src(tmp_path, src):
    """验证 files.src 的穿越、绝对路径和缺失文件均作为配置错误失败。"""
    asset_root = tmp_path / "smart-accel"
    asset_root.mkdir()

    with pytest.raises(SmartAccelConfigurationError):
        plan_scheme_files(
            [{"name": "target.conf", "src": src}],
            ctx(config_root=str(asset_root)),
        )


def test_plan_scheme_files_rejects_src_symlink_escape(tmp_path):
    """验证指向资产根外文件的 src 符号链接不能绕过目录边界。"""
    asset_root = tmp_path / "smart-accel"
    asset_root.mkdir()
    external_file = tmp_path / "outside.conf"
    external_file.write_text("secret\n", encoding="utf-8")
    (asset_root / "linked.conf").symlink_to(external_file)

    with pytest.raises(SmartAccelConfigurationError):
        plan_scheme_files(
            [{"name": "target.conf", "src": "linked.conf"}],
            ctx(config_root=str(asset_root)),
        )


def test_plan_scheme_files_rejects_src_symlink_loop(tmp_path):
    """验证无法解析的 src 符号链接循环也会作为配置错误失败。"""
    asset_root = tmp_path / "smart-accel"
    asset_root.mkdir()
    loop = asset_root / "loop.conf"
    loop.symlink_to(loop)

    with pytest.raises(SmartAccelConfigurationError):
        plan_scheme_files(
            [{"name": "target.conf", "src": "loop.conf"}],
            ctx(config_root=str(asset_root)),
        )
# ── {= expr} 算术求值(content / cli_params / envs 通用)───────────────────────


def test_expr_arithmetic_floor_div():
    """{= memory_capacity_gb // gpu_count} 算术求值(8 // 4 = 2)。"""
    c = ctx(memory_capacity_gb=8, gpu_count=4)
    assert render_engine_config({"x": "{= memory_capacity_gb // gpu_count}"}, c) == {"x": "2"}


def test_expr_float_normalize():
    """整值浮点归一为整数(8/2→'4'),非整值保留(7/2→'3.5')。"""
    c = ctx()
    assert render_engine_config({"a": "{= 8 / 2}"}, c) == {"a": "4"}
    assert render_engine_config({"b": "{= 7 / 2}"}, c) == {"b": "3.5"}


def test_expr_paren_precedence():
    """括号与运算符优先级:((8 + 8) * 2) = 32。"""
    c = ctx(memory_capacity_gb=8)
    assert render_engine_config({"x": "{= (memory_capacity_gb + 8) * 2}"}, c) == {"x": "32"}


def test_expr_unknown_var_kept_literal():
    """未知变量(不在命名空间)→ 原样保留 {= ...},不抛异常。"""
    c = ctx()
    assert render_engine_config({"x": "{= nonexistent * 2}"}, c) == {"x": "{= nonexistent * 2}"}


def test_expr_rejects_call():
    """函数调用被白名单拒 → 原样保留(安全:max / __import__ 均不执行)。"""
    c = ctx()
    assert render_engine_config({"a": "{= max(1, 2)}"}, c) == {"a": "{= max(1, 2)}"}
    assert render_engine_config({"b": "{= __import__('os').system('x')}"}, c) == {
        "b": "{= __import__('os').system('x')}"
    }


def test_expr_in_files_content(monkeypatch, tmp_path):
    """files content 多行文本里 {name} 与 {= expr} 共存:{rank_ip}/{master_ip}/{lookup_server_worker_ids} + {= ...}。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    c = ctx(memory_capacity_gb=8, gpu_count=4, tp_size=4)
    planned = plan_scheme_files(
        [{"name": "mooncake.json",
          "content": "local = {rank_ip}\nmaster = {master_ip}\n"
                     "segment = {= memory_capacity_gb // gpu_count}GB\n"
                     "workers = {lookup_server_worker_ids}\n"}],
        c,
    )
    assert planned[0].content == (
        "local = ${RANK_IP}\nmaster = ${MASTER_IP}\n"
        "segment = 2GB\nworkers = 0,1,2,3\n"
    )
    assert planned[0].runtime_vars == ["MASTER_IP", "RANK_IP"]
    assert not (tmp_path / "mooncake.json").exists()
