"""Mooncake standalone-store 分布式 KV 缓存解析与交付计划。

本模块依据实际推理引擎选择受控 runtime：``vllm`` 使用 ``mooncake_cuda`` /
``xcache_cuda``，``vllm-ascend`` 使用 ``mooncake_npu`` / ``xcache_npu``。硬件
名称不参与 runtime 推断，避免 Ascend 硬件上的非 vLLM-Ascend 工作负载误装 NPU 包。

模型 YAML 始终负责声明 vLLM ``kv_transfer_config``。Mooncake 配置、环境和
Store/Master 启动资产则可选择：受控 runtime 回退、完整 YAML 文件交付，或显式
hybrid。YAML 只能提供受现有 ``files`` 计划机制约束的文件和结构化环境，不能注入
任意 pre-serve shell。
"""

from __future__ import annotations

import logging
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from wings_accel.render import (
    PlaceholderContext,
    extract_package_requirements,
    fill_envs,
    plan_scheme_files,
    render_engine_config,
)
from wings_accel.schemas import (
    DistributedKVCacheConfig,
    EngineParams,
    GeneratedFile,
    SmartAccelConfigurationError,
    _FeatureOutput,
)

logger = logging.getLogger(__name__)

_CONFIG_FILE = "mooncake.json"
_STORE_SCRIPT = "start_mooncake_store.sh"
_MASTER_SCRIPT = "start_mooncake_master.sh"
_YAML_SOURCE = "yaml"
_RUNTIME_FALLBACK_SOURCE = "runtime_fallback"
_ACCEL_VOLUME_PATH_ENV = "ACCEL_VOLUME_PATH"
_DEFAULT_ACCEL_VOLUME = "/accel-volume"


@dataclass(frozen=True)
class _MooncakeRuntime:
    """一个受控 Mooncake runtime 的闭合定义。"""

    runtime_id: str
    package_name: str
    supported_topologies: frozenset[str]
    supported_protocols: frozenset[str]


# 运行时只由实际 engine 名选择。不要按 hardware_family 判断，避免引擎/硬件耦合。
_MOONCAKE_RUNTIMES = {
    "vllm": _MooncakeRuntime(
        runtime_id="mooncake_cuda",
        package_name="xcache_cuda",
        supported_topologies=frozenset({"standalone", "multi_node"}),
        supported_protocols=frozenset({"rdma", "tcp"}),
    ),
    "vllm-ascend": _MooncakeRuntime(
        runtime_id="mooncake_npu",
        package_name="xcache_npu",
        supported_topologies=frozenset({"standalone", "multi_node"}),
        supported_protocols=frozenset({"ascend", "rdma", "tcp"}),
    ),
}


def resolve_mooncake_runtime(engine_name: str) -> _MooncakeRuntime:
    """按规范化引擎名返回 Mooncake runtime，未支持时确定性失败。"""
    normalized = str(engine_name or "vllm").strip().lower().replace("_", "-")
    runtime = _MOONCAKE_RUNTIMES.get(normalized)
    if runtime is None:
        raise SmartAccelConfigurationError(
            "distributed_kv_offload supports only vllm (mooncake_cuda) and "
            f"vllm-ascend (mooncake_npu), got engine={engine_name!r}"
        )
    return runtime


def _resolve_highest_package_version(package_name: str) -> str:
    """解析 accel-volume 中 package 的最高 PEP 440 版本目录。"""
    volume = Path(os.environ.get(_ACCEL_VOLUME_PATH_ENV, _DEFAULT_ACCEL_VOLUME))
    package_dir = volume / "packages" / package_name
    if not package_dir.is_dir():
        raise SmartAccelConfigurationError(
            "Mooncake transfer engine package not found in wings-accel artifact: "
            f"{package_dir} (set {_ACCEL_VOLUME_PATH_ENV} or rebuild the wings-accel image "
            f"with packages/{package_name}/)"
        )
    candidates: list[tuple[Version, str]] = []
    for child in package_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            candidates.append((Version(child.name), child.name))
        except InvalidVersion:
            logger.warning("skip non-PEP440 version directory %s under %s", child.name, package_dir)
    if not candidates:
        raise SmartAccelConfigurationError(f"no valid version directory found under {package_dir}")
    return max(candidates, key=lambda item: item[0])[1]


def _require_client_settings(scheme: Dict[str, Any]) -> Dict[str, Any]:
    """校验模型 YAML 中可审计的 Mooncake 固定网络参数。"""
    client = scheme.get("client")
    if not isinstance(client, dict):
        raise SmartAccelConfigurationError("distributed_kv_offload scheme requires a client mapping")
    for name in ("rpc_port", "master_rpc_port", "metadata_port", "metadata_path"):
        value = client.get(name)
        if name.endswith("_port"):
            if not isinstance(value, int) or not 1 <= value <= 65535:
                raise SmartAccelConfigurationError(
                    f"distributed_kv_offload client.{name} must be an integer in 1..65535"
                )
        elif not isinstance(value, str) or not value.startswith("/"):
            raise SmartAccelConfigurationError("distributed_kv_offload client.metadata_path must start with '/'")
    return client


def _validate_input(cfg: DistributedKVCacheConfig) -> None:
    """校验跨层输入，避免将不完整容量写入环境、JSON 或 shell。"""
    if not cfg.memory_offload_enabled or cfg.memory_capacity_gb <= 0:
        raise SmartAccelConfigurationError(
            "ENABLE_DISTRIBUTED_KV_OFFLOAD requires ENABLE_KV_MEM_OFFLOAD and a positive "
            'KV_MEM_OFFLOAD_SIZE (numeric GB or "auto" resolved by the estimator)'
        )
    if cfg.disk_offload_enabled and (not cfg.disk_path or cfg.disk_capacity_gb <= 0):
        raise SmartAccelConfigurationError(
            "disk offload requires KV_DISK_OFFLOAD_PATH and a positive KV_DISK_OFFLOAD_SIZE"
        )


def _normalize_topology(topology: Optional[str]) -> str:
    return str(topology or "standalone").strip().lower() or "standalone"


def _validate_runtime_scheme(
    scheme: Dict[str, Any],
    runtime: _MooncakeRuntime,
    cfg: DistributedKVCacheConfig,
    topology: Optional[str],
) -> None:
    """验证 engine/runtime/topology/protocol 是明确且兼容的组合。"""
    declared_runtime = str(scheme.get("runtime") or "").strip()
    if not declared_runtime:
        # 仅存量 CUDA YAML 可省略 runtime；NPU YAML 必须显式防止误装 CUDA 包。
        if runtime.runtime_id != "mooncake_cuda":
            raise SmartAccelConfigurationError("vllm-ascend distributed_kv_offload requires runtime: mooncake_npu")
    elif declared_runtime != runtime.runtime_id:
        raise SmartAccelConfigurationError(
            f"distributed_kv_offload runtime={declared_runtime!r} is incompatible with "
            f"the selected engine runtime {runtime.runtime_id!r}"
        )

    current_topology = _normalize_topology(topology)
    if current_topology not in runtime.supported_topologies:
        raise SmartAccelConfigurationError(
            f"{runtime.runtime_id} supports only {sorted(runtime.supported_topologies)}, "
            f"got topology={current_topology!r}"
        )
    protocol = str(cfg.protocol or "").strip().lower()
    if protocol and protocol not in runtime.supported_protocols:
        raise SmartAccelConfigurationError(
            f"{runtime.runtime_id} does not support KV_PROTOCOL={protocol!r}; "
            f"allowed={sorted(runtime.supported_protocols)}"
        )


def _delivery_definition(scheme: Dict[str, Any], ctx: PlaceholderContext) -> tuple[str, dict[str, str], dict[str, str]]:
    """规范化并校验 delivery，返回模式、组件来源和 Mooncake env 覆盖。

    ``files`` 仍通过统一 GeneratedFile 机制交付；delivery 只决定每个组件是否必须
    由 YAML 提供还是允许当前 runtime 的受控资产回退。
    """
    raw = scheme.get("delivery")
    if raw is None:
        # 对存量 GPU 资产保持兼容：已有文件使用 YAML，缺项按 runtime 资产回退。
        return "legacy", {}, {}
    if not isinstance(raw, dict):
        raise SmartAccelConfigurationError("distributed_kv_offload delivery must be a mapping")

    mode = str(raw.get("mode") or "").strip().lower()
    if mode not in {"fallback", "full_yaml", "hybrid"}:
        raise SmartAccelConfigurationError(
            "distributed_kv_offload delivery.mode must be fallback, full_yaml, or hybrid"
        )

    envs = raw.get("envs", {})
    if envs is None:
        envs = {}
    if not isinstance(envs, dict):
        raise SmartAccelConfigurationError("distributed_kv_offload delivery.envs must be a mapping")
    env_overrides = fill_envs(envs, ctx)

    if mode == "fallback":
        if raw.get("components") is not None:
            raise SmartAccelConfigurationError("delivery.components is only valid for mode: hybrid")
        return (
            mode,
            {
                "env": _RUNTIME_FALLBACK_SOURCE,
                "config": _RUNTIME_FALLBACK_SOURCE,
                "store": _RUNTIME_FALLBACK_SOURCE,
                "master": _RUNTIME_FALLBACK_SOURCE,
            },
            env_overrides,
        )

    if mode == "full_yaml":
        if raw.get("components") is not None:
            raise SmartAccelConfigurationError("delivery.components is only valid for mode: hybrid")
        if not env_overrides:
            raise SmartAccelConfigurationError("delivery.mode=full_yaml requires a non-empty delivery.envs mapping")
        return (
            mode,
            {"env": _YAML_SOURCE, "config": _YAML_SOURCE, "store": _YAML_SOURCE, "master": _YAML_SOURCE},
            env_overrides,
        )

    components = raw.get("components")
    if not isinstance(components, dict):
        raise SmartAccelConfigurationError("delivery.mode=hybrid requires a components mapping")
    required = {"env", "config", "store", "master"}
    if set(components) != required:
        raise SmartAccelConfigurationError("delivery.components must contain exactly env, config, store, and master")
    sources: dict[str, str] = {}
    for name in sorted(required):
        source = str(components[name] or "").strip().lower()
        if source == "fallback":
            sources[name] = _RUNTIME_FALLBACK_SOURCE
        elif source == "yaml":
            sources[name] = _YAML_SOURCE
        else:
            raise SmartAccelConfigurationError(f"delivery.components.{name} must be yaml or fallback")
    if sources["env"] == _YAML_SOURCE and not env_overrides:
        raise SmartAccelConfigurationError("delivery.components.env=yaml requires delivery.envs")
    return mode, sources, env_overrides


def _validate_yaml_components(
    component_sources: dict[str, str],
    files_by_name: dict[str, GeneratedFile],
) -> None:
    """确保 delivery 声明为 YAML 的每个文件组件真的被当前模型 YAML 交付。"""
    required_files = {
        "config": _CONFIG_FILE,
        "store": _STORE_SCRIPT,
        "master": _MASTER_SCRIPT,
    }
    for component, filename in required_files.items():
        if component_sources[component] == _YAML_SOURCE and filename not in files_by_name:
            raise SmartAccelConfigurationError(
                f"delivery declares {component}=yaml but files does not provide {filename}"
            )


def _resolve_transfer_engine(
    result: _FeatureOutput,
    cfg: DistributedKVCacheConfig,
    runtime: _MooncakeRuntime,
    component_sources: dict[str, str],
) -> None:
    """选择 runtime 匹配的 xcache package；禁止 YAML pin 另一种 runtime。"""
    xcache_requirements = [
        req
        for req in result.packages
        if req.canonical_name in {canonicalize_name("xcache_cuda"), canonicalize_name("xcache_npu")}
    ]
    wrong = [
        req.manifest for req in xcache_requirements if req.canonical_name != canonicalize_name(runtime.package_name)
    ]
    if wrong:
        raise SmartAccelConfigurationError(
            f"{runtime.runtime_id} requires {runtime.package_name}, incompatible xcache package(s): {wrong}"
        )
    declared = next(
        (req for req in xcache_requirements if req.canonical_name == canonicalize_name(runtime.package_name)),
        None,
    )
    if declared is not None:
        component_sources["transfer_engine"] = _YAML_SOURCE
        result.mooncake_transfer_engine_package = declared.manifest
    elif cfg.install_transfer_engine:
        version = _resolve_highest_package_version(runtime.package_name)
        package_spec = f"{runtime.package_name}:{version}"
        result.packages = list(result.packages) + extract_package_requirements({"packages": [package_spec]})
        result.mooncake_transfer_engine_package = package_spec
        component_sources["transfer_engine"] = "injected"
        logger.info("injected %s transfer engine package: %s", runtime.runtime_id, package_spec)
    else:
        component_sources["transfer_engine"] = "disabled"
        logger.warning(
            "%s install disabled by ENABLE_XCACHE_INSTALL=false; assuming a compatible xcache "
            "runtime is preinstalled in the engine image",
            runtime.runtime_id,
        )


def smart_distributed_kv_offload_expander(
    cfg: DistributedKVCacheConfig,
    block: Any,
    ctx: PlaceholderContext,
    *,
    engine_name: str = "vllm",
    topology: Optional[str] = None,
) -> Optional[_FeatureOutput]:
    """选择并渲染 engine 对应的 Mooncake standalone-store YAML 方案。"""
    if not cfg.enabled:
        return None
    _validate_input(cfg)
    if block is None:
        return None
    if not isinstance(block, list) or len(block) != 1 or not isinstance(block[0], dict):
        raise SmartAccelConfigurationError("distributed_kv_offload must contain exactly one standalone-store scheme")

    runtime = resolve_mooncake_runtime(engine_name)
    scheme = block[0]
    _validate_runtime_scheme(scheme, runtime, cfg, topology)
    _require_client_settings(scheme)

    files = plan_scheme_files(
        scheme.get("files") or [],
        ctx,
        source_path_prefix=(
            f"{ctx.source_path}.distributed_kv_offload[0]" if ctx.source_path else "distributed_kv_offload[0]"
        ),
    )
    files_by_name = {file.path.rsplit("/", 1)[-1]: file for file in files}
    _delivery_mode, component_sources, env_overrides = _delivery_definition(scheme, ctx)
    if _delivery_mode in {"full_yaml", "hybrid"}:
        shared_root = Path(os.environ.get("SHARED_VOLUME_PATH", "/shared-volume")).resolve()
        runtime_root = shared_root / "distributed_offload" / runtime.runtime_id
        for generated_file in files:
            try:
                generated_path = Path(generated_file.path).resolve(strict=False)
            except OSError as exc:
                raise SmartAccelConfigurationError(
                    f"distributed_kv_offload file path is unresolvable: {generated_file.path!r}"
                ) from exc
            if not generated_path.is_relative_to(runtime_root):
                raise SmartAccelConfigurationError(
                    "runtime-aware distributed_kv_offload YAML files must stay under "
                    f"{runtime_root}: {generated_file.path!r}"
                )
    if _delivery_mode == "legacy":
        env_source = _YAML_SOURCE if scheme.get("envs") else _RUNTIME_FALLBACK_SOURCE
        config_source = _YAML_SOURCE if _CONFIG_FILE in files_by_name else _RUNTIME_FALLBACK_SOURCE
        store_source = _YAML_SOURCE if _STORE_SCRIPT in files_by_name else _RUNTIME_FALLBACK_SOURCE
        component_sources = {
            "env": env_source,
            "config": config_source,
            "store": store_source,
            # 保留旧 CUDA 语义：只有所有 Engine 组件均 YAML 交付时，才不生成回退 Master 段。
            "master": (
                _YAML_SOURCE
                if _MASTER_SCRIPT in files_by_name
                else "legacy_absent"
                if {env_source, config_source, store_source} == {_YAML_SOURCE}
                else _RUNTIME_FALLBACK_SOURCE
            ),
        }
        env_overrides = fill_envs(scheme.get("envs") or {}, ctx)
    _validate_yaml_components(component_sources, files_by_name)

    store_script = files_by_name.get(_STORE_SCRIPT)
    if store_script is not None and store_script.scope != "all":
        raise SmartAccelConfigurationError("start_mooncake_store.sh must have scope: all")
    master_script = files_by_name.get(_MASTER_SCRIPT)
    if master_script is not None and master_script.scope != "master":
        raise SmartAccelConfigurationError("start_mooncake_master.sh must have scope: master")

    envs = fill_envs(scheme.get("envs") or {}, ctx)
    config = files_by_name.get(_CONFIG_FILE)
    config_path = config.path if config is not None else ""

    # The standalone Store is the sole owner of Mooncake's SSD tier. Its
    # MOONCAKE_OFFLOAD_* settings are derived from client.env inside
    # start_mooncake_store.sh and must never enter the vLLM launcher env.
    result = _FeatureOutput(
        scheme=str(scheme.get("name") or "mooncake_standalone_store"),
        engine_params=EngineParams(
            env=envs,
            engine_config=render_engine_config(scheme.get("cli_params") or {}, ctx),
        ),
        packages=extract_package_requirements(scheme),
        pre_serve=[f"bash {shlex.quote(store_script.path)} &"] if store_script is not None else [],
        generated_files=files,
        mooncake_runtime=runtime.runtime_id,
        mooncake_env_overrides=env_overrides,
        mooncake_config_path=config_path,
        mooncake_env_files_required=True,
        mooncake_script_assets_required=any(
            source == _RUNTIME_FALLBACK_SOURCE for source in component_sources.values()
        ),
        mooncake_component_sources=component_sources,
        mooncake_master_script=master_script.path if master_script is not None else "",
    )
    return result


def apply_mooncake_script_fallback(
    cfg: DistributedKVCacheConfig,
    yaml_feature: Optional[_FeatureOutput],
    *,
    engine_name: str = "vllm",
    topology: Optional[str] = None,
) -> Optional[_FeatureOutput]:
    """补齐当前 runtime 未由 YAML 交付的可信 Mooncake 资产并注入正确 package。"""
    if not cfg.enabled:
        return yaml_feature
    _validate_input(cfg)
    if yaml_feature is None:
        raise SmartAccelConfigurationError("distributed_kv_offload scheme requires kv_transfer_config in cli_params")
    runtime = resolve_mooncake_runtime(engine_name)
    if _normalize_topology(topology) not in runtime.supported_topologies:
        raise SmartAccelConfigurationError(
            f"{runtime.runtime_id} does not support topology={_normalize_topology(topology)!r}"
        )

    result = yaml_feature
    component_sources = dict(result.mooncake_component_sources)
    if not component_sources:
        # 兼容直接调用本函数的旧测试/调用方。
        files_by_name = {file.path.rsplit("/", 1)[-1]: file for file in result.generated_files}
        component_sources = {
            "env": _RUNTIME_FALLBACK_SOURCE,
            "config": _YAML_SOURCE if _CONFIG_FILE in files_by_name else _RUNTIME_FALLBACK_SOURCE,
            "store": _YAML_SOURCE if _STORE_SCRIPT in files_by_name else _RUNTIME_FALLBACK_SOURCE,
            "master": _YAML_SOURCE if _MASTER_SCRIPT in files_by_name else _RUNTIME_FALLBACK_SOURCE,
        }
    if "kv_transfer_config" not in result.engine_params.engine_config:
        raise SmartAccelConfigurationError("distributed_kv_offload scheme requires kv_transfer_config in cli_params")

    _resolve_transfer_engine(result, cfg, runtime, component_sources)
    script_assets_required = any(
        component_sources[name] == _RUNTIME_FALLBACK_SOURCE for name in ("env", "config", "store", "master")
    )

    result.pre_serve.append('export SHARED_VOLUME_PATH="${SHARED_VOLUME_PATH:-/shared-volume}"')
    runtime_dir = f"$SHARED_VOLUME_PATH/distributed_offload/{runtime.runtime_id}"
    # Runtime assets own their role-specific environment files. The launcher only
    # exports the connector config path required by vLLM itself.
    if component_sources["config"] == _RUNTIME_FALLBACK_SOURCE:
        result.pre_serve.append(f'bash "{runtime_dir}/creat_mooncake_json.sh"')
    if component_sources["store"] == _RUNTIME_FALLBACK_SOURCE:
        result.pre_serve.append(f'bash "{runtime_dir}/start_mooncake_store.sh" &')
    master_source = component_sources["master"]
    if master_source == "legacy_absent":
        # 完全 YAML 的旧 CUDA 路径此前不交付 Master 生命周期，保持其零影响语义。
        result.mooncake_master_section = []
    else:
        master_script = result.mooncake_master_script or f"{runtime_dir}/start_mooncake_master.sh"
        result.mooncake_master_section = _render_mooncake_master_section(master_script, runtime.runtime_id)
    result.pre_serve.append(
        'echo "Mooncake distributed KV component sources: '
        f"runtime={runtime.runtime_id}, env={component_sources['env']}, "
        f"mooncake.json={component_sources['config']}, "
        f"start_mooncake_store.sh={component_sources['store']}, "
        f"start_mooncake_master.sh={component_sources['master']}, "
        f'transfer_config=yaml, transfer_engine={component_sources["transfer_engine"]}"'
    )
    result.pre_serve = list(dict.fromkeys(result.pre_serve))
    # 保持存量审计字段名，新增 runtime 与 Master 来源；内部 delivery 名称不泄漏到契约。
    fallback_source = "script_fallback" if runtime.runtime_id == "mooncake_cuda" else _RUNTIME_FALLBACK_SOURCE

    def audit_source(name: str) -> str:
        source = component_sources[name]
        return fallback_source if source == _RUNTIME_FALLBACK_SOURCE else source

    if runtime.runtime_id == "mooncake_cuda":
        # 存量 CUDA 审计契约保持不变；新 NPU/runtime-aware delivery 才增加 runtime/master 来源。
        result.mooncake_component_sources = {
            "mooncake.json": audit_source("config"),
            "start_mooncake_store.sh": audit_source("store"),
            "env": audit_source("env"),
            "transfer_config": _YAML_SOURCE,
            "transfer_engine": component_sources["transfer_engine"],
        }
    else:
        result.mooncake_component_sources = {
            "runtime": runtime.runtime_id,
            "env": audit_source("env"),
            "mooncake.json": audit_source("config"),
            "start_mooncake_store.sh": audit_source("store"),
            "start_mooncake_master.sh": audit_source("master"),
            "transfer_config": _YAML_SOURCE,
            "transfer_engine": component_sources["transfer_engine"],
        }
    result.mooncake_runtime = runtime.runtime_id
    result.mooncake_env_files_required = True
    result.mooncake_script_assets_required = script_assets_required
    return result


def _render_mooncake_master_section(master_script: str, runtime: str) -> list[str]:
    """生成 Master 专属 Pod early-exit 段；脚本路径来自可信 files 或 runtime assets。"""
    master_start = (
        f"bash {shlex.quote(master_script)}" if not master_script.startswith("$") else f'bash "{master_script}"'
    )
    return [
        "# ─── Mooncake master branch (IS_MOONCAKE_MASTER) ───",
        "# master Pod: only starts mooncake_master and never executes vllm serve.",
        'export SHARED_VOLUME_PATH="${SHARED_VOLUME_PATH:-/shared-volume}"',
        'if [ "${IS_MOONCAKE_MASTER:-}" = "TRUE" ] || [ "${IS_MOONCAKE_MASTER:-}" = "true" ] || \\',
        '   [ "${IS_MOONCAKE_MASTER:-}" = "1" ] || [ "${IS_MOONCAKE_MASTER:-}" = "True" ]; then',
        "    mkdir -p /var/log/wings",
        f"    {master_start} &",
        "    MASTER_PID=$!",
        '    _wings_log INFO "mooncake master started, PID=$MASTER_PID"',
        '    wait "$MASTER_PID"',
        '    exit "$?"',
        "fi",
        "",
    ]
