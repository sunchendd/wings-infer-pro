"""Mooncake standalone-store 分布式 KV 缓存回归测试。"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from wings_accel.distributed_offload import (
    apply_mooncake_script_fallback,
    smart_distributed_kv_offload_expander,
)
from wings_accel.render import PlaceholderContext
from wings_accel.schemas import DistributedKVCacheConfig, SmartAccelConfigurationError

_BASH = shutil.which("bash") or "/bin/bash"


def _ctx():
    # 重构后分布式运行时值(protocol/服务地址/buffer)不再经 PlaceholderContext 透传:
    # 它们由 DistributedKVCacheConfig 携带,或由脚本兜底(creat_mooncake_json.sh)在
    # shell 侧拼装;ctx 只承载介质容量/路径等通用占位符。
    return PlaceholderContext(
        memory_capacity_gb=32,
        memory_offload_enabled=True,
        disk_offload_enabled=True,
        disk_capacity_gb=128,
        disk_path="/mnt/mooncake",
    )


def _block():
    return [{
        "name": "mooncake_standalone_store",
        "client": {"rpc_port": 50052, "master_rpc_port": 50051, "metadata_port": 10080, "metadata_path": "/metadata"},
        "cli_params": {"kv_transfer_config": {"kv_connector": "MooncakeStoreConnector", "kv_role": "kv_both"}},
        "files": [
            {
                "path": "mooncake.json",
                "content": '{"mode":"standalone-store",'
                           '"metadata_server":"http://mooncake-service-order-7:10080/metadata",'
                           '"master_server_address":"mooncake-service-order-7:50051","global_segment_size":0,'
                           '"local_buffer_size":"1GB","protocol":"rdma","enable_offload":true}\n',
            },
            {
                "path": "start_mooncake_store.sh", "scope": "all", "mode": "0755",
                "content": "#!/usr/bin/env bash\nexec mooncake_client --port=\"${MOONCAKE_CLIENT_RPC_PORT}\"\n",
            },
        ],
    }]


def _partial_block(packages=None):
    """YAML 只提供 kv_transfer_config 锚点(三部件走脚本兜底)的最小 scheme。"""
    scheme = {
        "name": "partial_mooncake",
        "client": {"rpc_port": 50052, "master_rpc_port": 50051, "metadata_port": 10080, "metadata_path": "/metadata"},
        "cli_params": {"kv_transfer_config": {"kv_connector": "MooncakeStoreConnector", "kv_role": "kv_both"}},
        "files": [],
    }
    if packages is not None:
        scheme["packages"] = packages
    return [scheme]


def _accel_volume(tmp_path, monkeypatch, *versions):
    """构造 accel-volume 工件目录(packages/<name>/<version>/)并指向 ACCEL_VOLUME_PATH。"""
    root = tmp_path / "accel-volume"
    for version in versions:
        (root / "packages" / "xcache_cuda" / version).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ACCEL_VOLUME_PATH", str(root))
    return root


def test_distributed_mooncake_renders_client_for_all_nodes(monkeypatch, tmp_path):
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    cfg = DistributedKVCacheConfig(
        enabled=True, protocol="rdma", serving_config_id="order-7", local_buffer_size="1GB",
        memory_offload_enabled=True, memory_capacity_gb=32,
        disk_offload_enabled=True, disk_capacity_gb=128, disk_path="/mnt/mooncake",
    )

    output = smart_distributed_kv_offload_expander(cfg, _block(), _ctx())

    assert output.scheme == "mooncake_standalone_store"
    assert output.engine_params.engine_config["kv_transfer_config"]["kv_connector"] == "MooncakeStoreConnector"
    # YAML 提供 mooncake.json 时,env 只落 MOONCAKE_CONFIG_PATH 指向实际落盘路径;
    # 其余运行时变量由 env.yaml → client.env(脚本兜底)透传,MOONCAKE_PREFERRED_SEGMENT
    # 等派生值已随重构移除。
    assert output.engine_params.env["MOONCAKE_CONFIG_PATH"] == str(tmp_path / "mooncake.json")
    assert output.engine_params.env["MOONCAKE_OFFLOAD_FILE_STORAGE_PATH"] == "/mnt/mooncake"
    assert output.engine_params.env["MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES"] == str(128 * 1024**3)
    assert output.pre_serve == [f"bash {tmp_path}/start_mooncake_store.sh &"]
    config = json.loads(next(item.content for item in output.generated_files if item.path.endswith("mooncake.json")))
    assert config == {
        "mode": "standalone-store",
        "metadata_server": "http://mooncake-service-order-7:10080/metadata",
        "master_server_address": "mooncake-service-order-7:50051",
        "global_segment_size": 0,
        "local_buffer_size": "1GB",
        "protocol": "rdma",
        "enable_offload": True,
    }


@pytest.mark.parametrize("field,value", [("disk_path", ""), ("disk_capacity_gb", 0)])
def test_distributed_mooncake_rejects_unsafe_required_values(monkeypatch, tmp_path, field, value):
    """disk offload 开启但路径/容量非法 → fail-fast（KV_PROTOCOL 等 env 由脚本侧校验）。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    kwargs = dict(
        enabled=True, protocol="rdma", serving_config_id="order-7", local_buffer_size="1GB",
        memory_offload_enabled=True, memory_capacity_gb=32,
        disk_offload_enabled=True, disk_capacity_gb=128, disk_path="/mnt/mooncake",
    )
    kwargs[field] = value
    with pytest.raises(SmartAccelConfigurationError):
        smart_distributed_kv_offload_expander(DistributedKVCacheConfig(**kwargs), _block(), _ctx())


def test_distributed_mooncake_requires_memory_capacity(monkeypatch, tmp_path):
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    cfg = DistributedKVCacheConfig(enabled=True, protocol="tcp", serving_config_id="order-7", local_buffer_size="1GB")
    with pytest.raises(SmartAccelConfigurationError, match="KV_MEM_OFFLOAD_SIZE"):
        smart_distributed_kv_offload_expander(cfg, _block(), _ctx())


def test_auto_estimate_below_threshold_disables_expander():
    """auto 估算不足 → loader 在与本地同一分支置 enabled=False → expander 自然不产出。"""
    cfg = DistributedKVCacheConfig(
        enabled=False, protocol="rdma", serving_config_id="order-7", local_buffer_size="1GB",
        memory_offload_size_mode="auto", memory_offload_enabled=False, memory_capacity_gb=0,
    )

    assert smart_distributed_kv_offload_expander(cfg, _block(), _ctx()) is None


def test_auto_estimate_below_threshold_disables_script_fallback():
    """auto 估算不足 → loader 已置 enabled=False → 脚本兜底同样不产出任何部件。"""
    cfg = DistributedKVCacheConfig(
        enabled=False, protocol="rdma", serving_config_id="order-7", local_buffer_size="1GB",
        memory_offload_size_mode="auto", memory_offload_enabled=False, memory_capacity_gb=0,
    )

    assert apply_mooncake_script_fallback(cfg, None) is None


def test_auto_estimate_effective_still_produces(monkeypatch, tmp_path):
    """auto 估算生效(memory_capacity_gb>0)→ 与数值模式同样正常产出。"""
    monkeypatch.setenv("SHARED_VOLUME_PATH", str(tmp_path))
    cfg = DistributedKVCacheConfig(
        enabled=True, protocol="rdma", serving_config_id="order-7", local_buffer_size="1GB",
        memory_offload_size_mode="auto", memory_offload_enabled=True, memory_capacity_gb=171,
    )

    output = smart_distributed_kv_offload_expander(cfg, _block(), _ctx())

    assert output is not None
    assert output.scheme == "mooncake_standalone_store"


def test_distributed_mooncake_uses_script_fallback_for_missing_yaml_parts(tmp_path, monkeypatch):
    """YAML 有 kv_transfer_config（锚点）时，json/client/env 三部件逐项回退到脚本。"""
    _accel_volume(tmp_path, monkeypatch, "v0.3.12.post1")
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
    )

    yaml_feature = smart_distributed_kv_offload_expander(cfg, _partial_block(), _ctx())
    output = apply_mooncake_script_fallback(cfg, yaml_feature)

    assert output is not None
    assert output.mooncake_component_sources == {
        "mooncake.json": "script_fallback",
        "start_mooncake_store.sh": "script_fallback",
        "env": "script_fallback",
        "transfer_config": "yaml",
        "transfer_engine": "injected",
    }
    assert output.mooncake_script_assets_required is True
    assert output.engine_params.engine_config["kv_transfer_config"] == {
        "kv_connector": "MooncakeStoreConnector",
        "kv_role": "kv_both",
    }
    assert 'bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_store.sh" &' in output.pre_serve
    assert any("Mooncake distributed KV component sources" in line for line in output.pre_serve)
    # 默认注入:YAML 未声明 packages → 按 accel-volume 工件最高版本注入 transfer engine。
    assert [req.manifest for req in output.packages] == ["xcache_cuda:v0.3.12.post1"]
    # 注入的传输引擎包单独透传:master Pod 交付支线据此渲染只含该包的 install 段
    # (mooncake_master 二进制来源,见 docs/contracts/wings-accel-interface.md)。
    assert output.mooncake_transfer_engine_package == "xcache_cuda:v0.3.12.post1"


def test_script_fallback_sources_engine_environment_before_client_start():
    """脚本回退环境必须由受控 env 文件加载，不能散落在 Python 渲染结果中。"""
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
        disk_offload_enabled=True,
        disk_capacity_gb=128,
        disk_path="/mnt/mooncake",
    )


def test_script_fallback_rejects_missing_transfer_config():
    """新策略:kv_transfer_config 必须由 YAML 提供,缺失 → 报错。"""
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
        disk_offload_enabled=True,
        disk_capacity_gb=128,
        disk_path="/mnt/mooncake",
    )

    with pytest.raises(SmartAccelConfigurationError, match="kv_transfer_config"):
        apply_mooncake_script_fallback(cfg, None)


def test_script_fallback_requires_kv_transfer_config_from_yaml():
    """新策略:smart yaml 必须有 kv_transfer_config,缺失 → 报错(不再脚本兜底)。"""
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
    )

    with pytest.raises(SmartAccelConfigurationError, match="kv_transfer_config"):
        apply_mooncake_script_fallback(cfg, None)


def test_script_fallback_json_writes_vllm_mooncake_config(tmp_path):
    """脚本兜底 JSON 只读取受限环境变量，并原子写入共享卷目标。"""
    import wings_accel.distributed_offload as distributed_offload

    script = Path(distributed_offload.__file__).parent / "distributed_offload" / "mooncake" / "creat_mooncake_json.sh"
    env = {
        **os.environ,
        "SHARED_VOLUME_PATH": str(tmp_path),
        "SERVING_CONFIG_ID": "order-7",
        "KV_PROTOCOL": "rdma",
        "KV_MEM_OFFLOAD_SIZE": "1",
        "ENABLE_KV_MEM_OFFLOAD": "true",
        "ENABLE_KV_DISK_OFFLOAD": "true",
    }

    subprocess.run([_BASH, str(script)], check=True, env=env, capture_output=True, text=True)

    # local_buffer_size 不在 JSON 里:engine 侧缓冲由 client.env 的 KV_LOCAL_BUFFER_SIZE
    # 传递(不再由 KV_MEM_OFFLOAD_SIZE 派生,容量与缓冲职责分离)。
    assert json.loads((tmp_path / "mooncake" / "mooncake.json").read_text()) == {
        "mode": "standalone-store",
        "metadata_server": "http://mooncake-service-order-7:10080/metadata",
        "master_server_address": "mooncake-service-order-7:50051",
        "global_segment_size": 0,
        "protocol": "rdma",
        "device_name": "",
        "enable_offload": True,
    }


@pytest.mark.parametrize("topology", ["standalone", "multi_node"])
def test_target_asset_routes_mooncake_for_supported_topologies(topology, tmp_path, monkeypatch):
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import LoadFlags, _package_smart_accel_root

    _accel_volume(tmp_path, monkeypatch, "v0.3.12.post1")
    output = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm",
        engine_version="v0.23.0",
        hardware_family="l20",
        model_name="DeepSeek-R1-Distill-Qwen-1.5B",
        gpu_count=1,
        flags=LoadFlags(
            topology=topology,
            distributed_kv=True,
            distributed_protocol="rdma",
            serving_config_id="order-7",
            distributed_local_buffer_size="1GB",
            memory_offload_size_mode="32",
        ),
    )

    assert output is not None
    assert output.smart_distributed_kv_cache_scheme == "mooncake_standalone_store"
    assert output.engine_params.engine_config["kv_transfer_config"]["kv_connector"] == "MooncakeStoreConnector"
    # pre_serve 现在是受控脚本兜底管线(export/source/creat_json/client 启动/审计 echo);
    # client 启动行不再位于首位,按精确整行断言。
    assert 'bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_store.sh" &' in output.pre_serve
    # 全链路(含脚本兜底)同样注入默认 transfer engine 包,流经 install.py 段。
    assert "xcache_cuda:v0.3.12.post1" in output.packages


@pytest.mark.parametrize("topology", ["standalone", "multi_node"])
def test_v4_flash_0731_h20_routes_mooncake_for_supported_topologies(topology, tmp_path, monkeypatch):
    """DeepSeek-V4-Flash-0731(v0.26.0/h20_141G)distributed_kv_offload 适配资产的路由守护。

    参考 1.5B 资产的同等断言:variant 精确命中 0731 文件(variant_name 优先于
    fp8 家族 name_pattern),standalone/multi_node 两拓扑均产出 Mooncake standalone-store
    (kv_transfer_config 锚点 + 受控脚本兜底 + 默认 transfer engine 包注入)。
    PD 拓扑不声明 distributed_kv_offload,不在本测试参数化内(缺键即不产出)。
    """
    from wings_accel import resolve_smart_accel_from_config
    from wings_accel.yaml_loader import LoadFlags, _package_smart_accel_root

    _accel_volume(tmp_path, monkeypatch, "v0.3.12.post1")
    output = resolve_smart_accel_from_config(
        config_root=_package_smart_accel_root().parent,
        engine="vllm",
        engine_version="v0.26.0",
        hardware_family="h20_141G",
        model_name="DeepSeek-V4-Flash-0731",
        gpu_count=8,
        flags=LoadFlags(
            topology=topology,
            distributed_kv=True,
            distributed_protocol="rdma",
            serving_config_id="order-7",
            distributed_local_buffer_size="1GB",
            memory_offload_size_mode="32",
        ),
    )

    assert output is not None
    assert output.smart_distributed_kv_cache_scheme == "mooncake_standalone_store"
    kt = output.engine_params.engine_config["kv_transfer_config"]
    assert kt["kv_connector"] == "MooncakeStoreConnector"
    assert kt["kv_role"] == "kv_both"
    assert kt["kv_load_failure_policy"] == "recompute"
    assert 'bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_store.sh" &' in output.pre_serve
    assert "xcache_cuda:v0.3.12.post1" in output.packages


def test_script_fallback_synthesizes_mooncake_master_section(tmp_path, monkeypatch):
    """脚本兜底被选中时,master 分支段应包含 master.env source + master 拉起 + early-exit。"""
    _accel_volume(tmp_path, monkeypatch, "v0.3.12.post1")
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
    )
    ctx = PlaceholderContext(
        memory_capacity_gb=32,
        memory_offload_enabled=True,
        disk_offload_enabled=True,
        disk_capacity_gb=128,
        disk_path="/mnt/mooncake",
    )
    yaml_feature = smart_distributed_kv_offload_expander(cfg, _block(), ctx)
    output = apply_mooncake_script_fallback(cfg, yaml_feature)

    section = "\n".join(output.mooncake_master_section)
    assert "IS_MOONCAKE_MASTER" in section
    assert 'source "$SHARED_VOLUME_PATH/mooncake/master.env"' in section
    # 后台拉起且不做输出重定向:master.sh 自带日志处理,stdout/stderr 流向 engine.log。
    assert 'bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_master.sh" &' in section
    assert ">>" not in section
    assert "wait \"$MASTER_PID\"" in section
    assert "exit \"$?\"" in section


def test_script_fallback_skips_master_section_when_yaml_only():
    """master 分支段仅在脚本兜底被选中时合成;YAML-only 路径不产出(零影响)。"""
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
    )
    ctx = PlaceholderContext(
        memory_capacity_gb=32,
        memory_offload_enabled=True,
        disk_offload_enabled=True,
        disk_capacity_gb=128,
        disk_path="/mnt/mooncake",
    )
    yaml_feature = smart_distributed_kv_offload_expander(cfg, _block(), ctx)
    # YAML 已提供全部四部件 → 无需脚本兜底,master 段不合成。
    assert yaml_feature is not None
    assert yaml_feature.mooncake_master_section == []


def test_fallback_injects_highest_available_version(tmp_path, monkeypatch):
    """YAML 未钉版本 → 注入 accel-volume 工件中该包的最高版本(PEP 440 排序)。"""
    _accel_volume(tmp_path, monkeypatch, "v0.3.10", "v0.3.12.post1", "not-a-version")
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
    )

    output = apply_mooncake_script_fallback(
        cfg, smart_distributed_kv_offload_expander(cfg, _partial_block(), _ctx())
    )

    assert [req.manifest for req in output.packages] == ["xcache_cuda:v0.3.12.post1"]


def test_fallback_yaml_declared_version_overrides_default(tmp_path, monkeypatch):
    """YAML scheme 显式声明同名包 → 声明优先,不注入、也不解析 accel-volume。"""
    monkeypatch.delenv("ACCEL_VOLUME_PATH", raising=False)
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
    )

    output = apply_mooncake_script_fallback(
        cfg,
        smart_distributed_kv_offload_expander(
            cfg, _partial_block(packages={"xcache_cuda": "v0.3.10"}), _ctx()
        ),
    )

    assert [req.manifest for req in output.packages] == ["xcache_cuda:v0.3.10"]


def test_fallback_requires_accel_volume_when_unpinned(tmp_path, monkeypatch):
    """YAML 未钉版本且工件缺包目录 → fail-fast(SmartAccelConfigurationError)。"""
    monkeypatch.setenv("ACCEL_VOLUME_PATH", str(tmp_path / "missing-accel-volume"))
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
    )

    with pytest.raises(SmartAccelConfigurationError, match="wings-accel artifact"):
        apply_mooncake_script_fallback(
            cfg, smart_distributed_kv_offload_expander(cfg, _partial_block(), _ctx())
        )


def test_fallback_skips_injection_when_install_disabled(tmp_path, monkeypatch, caplog):
    """install_transfer_engine=False(ENABLE_XCACHE_INSTALL=false)→ 不注入、不解析 accel-volume。

    与 fail-fast 用例同环境(工件目录缺失)但开关关闭:证明注入路径被整体跳过,
    且来源审计与启动日志标注 transfer_engine=disabled。
    """
    monkeypatch.setenv("ACCEL_VOLUME_PATH", str(tmp_path / "missing-accel-volume"))
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
        install_transfer_engine=False,
    )

    with caplog.at_level("WARNING", logger="wings_accel.distributed_offload"):
        output = apply_mooncake_script_fallback(
            cfg, smart_distributed_kv_offload_expander(cfg, _partial_block(), _ctx())
        )

    assert output is not None
    assert output.packages == []
    assert output.mooncake_component_sources["transfer_engine"] == "disabled"
    # 开关关闭 → 未注入:不透传传输引擎包(master 交付不渲染 install 段,镜像预装兜底)。
    assert output.mooncake_transfer_engine_package is None
    echo = next(line for line in output.pre_serve if "component sources" in line)
    assert "transfer_engine=disabled" in echo
    assert "preinstalled" in caplog.text


def test_fallback_disabled_install_keeps_yaml_declaration(tmp_path, monkeypatch):
    """开关只管注入路径:YAML 显式声明同名包 → 声明仍优先,包不丢(声明优先不受开关影响)。"""
    monkeypatch.delenv("ACCEL_VOLUME_PATH", raising=False)
    cfg = DistributedKVCacheConfig(
        enabled=True,
        protocol="rdma",
        serving_config_id="order-7",
        local_buffer_size="1GB",
        memory_offload_enabled=True,
        memory_capacity_gb=32,
        install_transfer_engine=False,
    )

    output = apply_mooncake_script_fallback(
        cfg,
        smart_distributed_kv_offload_expander(
            cfg, _partial_block(packages={"xcache_cuda": "v0.3.10"}), _ctx()
        ),
    )

    assert [req.manifest for req in output.packages] == ["xcache_cuda:v0.3.10"]
    assert output.mooncake_component_sources["transfer_engine"] == "yaml"
    # YAML 声明优先:透传声明的原始 name:version(manifest 键,原样交付)。
    assert output.mooncake_transfer_engine_package == "xcache_cuda:v0.3.10"
