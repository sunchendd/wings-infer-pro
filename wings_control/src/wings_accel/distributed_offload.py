"""Mooncake standalone-store 分布式 KV 缓存渲染。

本模块与 ``offload.py`` 并列：本地 KV 卸载和 Mooncake standalone-store 都会
写入 vLLM 的 ``kv_transfer_config``，因此不能共用同一个选择器或同时产出。
Mooncake master 由部署侧管理；这里仅为每个 engine Pod 交付并启动 real client。
"""

import logging
import os
import shlex
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
    SmartAccelConfigurationError,
    _FeatureOutput,
)

logger = logging.getLogger(__name__)

_CLIENT_SCRIPT = "start_mooncake_store.sh"
_MASTER_SCRIPT = "start_mooncake_master.sh"
_CONFIG_FILE = "mooncake.json"
_ENGINE_ENV_FILE = "client.env"
_YAML_SOURCE = "yaml"
_SCRIPT_FALLBACK_SOURCE = "script_fallback"

# Mooncake transfer engine 经 install.py 安装的默认包(manifest 键 = wings-accel
# packages/ 目录名;包名已由 mooncake_non_cuda 更名为 xcache_non_cuda)。特性级
# 前提依赖:任何模型开启分布式 KV 卸载都须安装,故在代码收口注入而非逐模型 YAML
# 声明;YAML scheme 显式声明同名包时声明优先(可钉特殊版本)。版本本身不在此
# 钉死 —— 由 accel-volume 镜像内容决定(见 _resolve_highest_package_version),
# 升级只需重建 wings-accel 镜像。
_TRANSFER_ENGINE_PACKAGE = "xcache_non_cuda"
# wings-accel 工件在容器内的挂载路径(install.py / packages/ 所在);与
# script_builder 生成 install.py 行的 /accel-volume 硬编码保持同源,测试经
# 同名环境变量指向临时目录。
_ACCEL_VOLUME_PATH_ENV = "ACCEL_VOLUME_PATH"
_DEFAULT_ACCEL_VOLUME = "/accel-volume"


def _resolve_highest_package_version(package_name: str) -> str:
    """解析包在 accel-volume 工件中的最高版本(PEP 440 排序,返回目录名原样)。

    版本以 wings-accel 镜像为单一真相源:packages/<name>/<version>/ 目录名即
    install.py manifest 键。YAML 未钉版本时取最高版本,镜像升级后无需改代码。

    Raises:
        SmartAccelConfigurationError: 包目录缺失、或无任何合法版本目录
            (fail-fast:mooncake 无法安装则特性必然失效,不让 pod 带到运行期才崩)。
    """
    volume = Path(os.environ.get(_ACCEL_VOLUME_PATH_ENV, _DEFAULT_ACCEL_VOLUME))
    package_dir = volume / "packages" / package_name
    if not package_dir.is_dir():
        raise SmartAccelConfigurationError(
            f"xcache transfer engine package not found in wings-accel artifact: "
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
            logger.warning(
                "skip non-PEP440 version directory %s under %s", child.name, package_dir
            )
    if not candidates:
        raise SmartAccelConfigurationError(
            f"no valid version directory found under {package_dir}"
        )
    return max(candidates, key=lambda item: item[0])[1]


def _require_client_settings(scheme: Dict[str, Any]) -> Dict[str, Any]:
    """校验 YAML 中可审计的 Mooncake client 固定参数。"""
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
            raise SmartAccelConfigurationError(
                "distributed_kv_offload client.metadata_path must start with '/'"
            )
    return client


def _validate_input(cfg: DistributedKVCacheConfig) -> None:
    """验证来自 MaaS 的分布式缓存输入，避免写入 shell/JSON 前才失败。

    只校验跨层耦合字段（内存卸载开关/容量）；KV_PROTOCOL / SERVING_CONFIG_ID /
    KV_LOCAL_BUFFER_SIZE 等由 env.yaml 默认值 + client.env 透传，脚本侧
    （creat_mooncake_json.sh / start_mooncake_store.sh）自带校验。
    """
    if not cfg.memory_offload_enabled or cfg.memory_capacity_gb <= 0:
        raise SmartAccelConfigurationError(
            "ENABLE_DISTRIBUTED_KV_OFFLOAD requires ENABLE_KV_MEM_OFFLOAD and a positive KV_MEM_OFFLOAD_SIZE"
        )
    if cfg.disk_offload_enabled and (not cfg.disk_path or cfg.disk_capacity_gb <= 0):
        raise SmartAccelConfigurationError(
            "disk offload requires KV_DISK_OFFLOAD_PATH and a positive KV_DISK_OFFLOAD_SIZE"
        )


def smart_distributed_kv_offload_expander(
    cfg: DistributedKVCacheConfig,
    block: Any,
    ctx: PlaceholderContext,
) -> Optional[_FeatureOutput]:
    """选择并渲染 Mooncake standalone-store 方案。

    YAML 决定 connector、固定端口、配置文件及启动脚本；运行时环境只提供开关、
    容量、协议和实例 id。脚本由所有节点在 vLLM 前后台启动，master 不在此路径启动。
    """
    if not cfg.enabled:
        return None
    _validate_input(cfg)
    # ``distributed_kv_offload`` 未在匹配 YAML 中声明并不是配置错误：脚本兜底
    # 会在本 expander 返回后补齐四个部件。
    if block is None:
        return None
    if not isinstance(block, list) or len(block) != 1 or not isinstance(block[0], dict):
        raise SmartAccelConfigurationError(
            "distributed_kv_offload must contain exactly one standalone-store scheme"
        )
    scheme = block[0]
    files = plan_scheme_files(
        scheme.get("files") or [],
        ctx,
        source_path_prefix=f"{ctx.source_path}.distributed_kv_offload[0]" if ctx.source_path else "distributed_kv_offload[0]",
    )
    by_name = {file.path.rsplit("/", 1)[-1]: file for file in files}
    config = by_name.get(_CONFIG_FILE)
    script = by_name.get(_CLIENT_SCRIPT)
    if script is not None and script.scope != "all":
        raise SmartAccelConfigurationError("start_mooncake_store.sh must have scope: all")

    envs = fill_envs(scheme.get("envs") or {}, ctx)
    # YAML 提供 mooncake.json 时只 export MOONCAKE_CONFIG_PATH 指向实际落盘路径；
    # 其余环境变量由 env.yaml → client.env 链路（脚本兜底）统一透传给 engine，
    # 支持四个部件分别回退。
    if config is not None:
        _require_client_settings(scheme)
        envs.update(
            {
                "MOONCAKE_CONFIG_PATH": config.path,
            }
        )
        if cfg.disk_offload_enabled:
            envs["MOONCAKE_OFFLOAD_FILE_STORAGE_PATH"] = cfg.disk_path
            envs["MOONCAKE_OFFLOAD_TOTAL_SIZE_LIMIT_BYTES"] = str(cfg.disk_capacity_gb * 1024**3)

    return _FeatureOutput(
        scheme=str(scheme.get("name") or "mooncake_standalone_store"),
        engine_params=EngineParams(
            env=envs,
            engine_config=render_engine_config(scheme.get("cli_params") or {}, ctx),
        ),
        packages=extract_package_requirements(scheme),
        pre_serve=[f"bash {shlex.quote(script.path)} &"] if script is not None else [],
        generated_files=files,
    )


def apply_mooncake_script_fallback(
    cfg: DistributedKVCacheConfig,
    yaml_feature: Optional[_FeatureOutput],
) -> Optional[_FeatureOutput]:
    """按部件将未由 YAML 产出的 Mooncake 配置回退到受控脚本。

    新策略:``kv_transfer_config`` 是 smart-accel YAML 的**必填锚点**——未由 YAML
    声明时抛 ``SmartAccelConfigurationError``(不再脚本兜底)。其余三部件
    (mooncake.json / start_mooncake_store.sh / env)缺失时逐项回退到受控脚本;
    已经由 YAML 提供的部件不会被覆盖。返回的命令均由受控包代码合成,不接受
    YAML 中的任意 shell 内容。
    """
    if not cfg.enabled:
        return yaml_feature
    _validate_input(cfg)

    result = yaml_feature or _FeatureOutput(
        scheme="mooncake_standalone_store",
        engine_params=EngineParams(),
    )
    files_by_name = {
        file.path.rsplit("/", 1)[-1]: file for file in result.generated_files
    }
    component_sources = {
        "mooncake.json": _YAML_SOURCE if _CONFIG_FILE in files_by_name else _SCRIPT_FALLBACK_SOURCE,
        "start_mooncake_store.sh": _YAML_SOURCE if _CLIENT_SCRIPT in files_by_name else _SCRIPT_FALLBACK_SOURCE,
        "env": _YAML_SOURCE if "MOONCAKE_CONFIG_PATH" in result.engine_params.env else _SCRIPT_FALLBACK_SOURCE,
        "transfer_config": _YAML_SOURCE if "kv_transfer_config" in result.engine_params.engine_config else _SCRIPT_FALLBACK_SOURCE,
    }
    if component_sources["transfer_config"] == _SCRIPT_FALLBACK_SOURCE:
        # kv_transfer_config 必须由 YAML 声明:缺失是确定性配置错误,fail-fast。
        raise SmartAccelConfigurationError(
            "distributed_kv_offload scheme requires kv_transfer_config in cli_params"
        )

    # transfer engine 默认包注入:YAML scheme 未声明同名包时,按 accel-volume 工件
    # 的最高版本注入(install.py 段随之产出,卸载+安装由包内 install.sh 完成)。
    # 声明优先:YAML 已钉版本 → 不注入、不解析(可借此锁定非默认版本)。
    transfer_engine_canonical = canonicalize_name(_TRANSFER_ENGINE_PACKAGE)
    if all(req.canonical_name != transfer_engine_canonical for req in result.packages):
        version = _resolve_highest_package_version(_TRANSFER_ENGINE_PACKAGE)
        result.packages = list(result.packages) + extract_package_requirements(
            {"packages": [f"{_TRANSFER_ENGINE_PACKAGE}:{version}"]}
        )
        logger.info(
            "injected default xcache transfer engine package: %s:%s",
            _TRANSFER_ENGINE_PACKAGE,
            version,
        )

    script_assets_required = (
        component_sources["mooncake.json"] == _SCRIPT_FALLBACK_SOURCE
        or component_sources["start_mooncake_store.sh"] == _SCRIPT_FALLBACK_SOURCE
        or component_sources["env"] == _SCRIPT_FALLBACK_SOURCE
    )
    if script_assets_required:
        # 每个 engine 节点在 vLLM 前加载受控环境，再生成本节点的配置并后台启动 client。
        result.pre_serve.extend(
            [
                'export SHARED_VOLUME_PATH="${SHARED_VOLUME_PATH:-/shared-volume}"',
            ]
        )
        if component_sources["env"] == _SCRIPT_FALLBACK_SOURCE:
            # YAML 提供 JSON、但未提供环境时，仍须让 env 文件使用 YAML 的实际落盘路径。
            if component_sources["mooncake.json"] == _YAML_SOURCE:
                result.pre_serve.append(
                    "export MOONCAKE_SCRIPT_FALLBACK_CONFIG_PATH="
                    f"{shlex.quote(files_by_name[_CONFIG_FILE].path)}"
                )
            result.pre_serve.append(
                f'source "$SHARED_VOLUME_PATH/mooncake/{_ENGINE_ENV_FILE}"'
            )
        if component_sources["mooncake.json"] == _SCRIPT_FALLBACK_SOURCE:
            result.pre_serve.append(
                'bash "$SHARED_VOLUME_PATH/mooncake/creat_mooncake_json.sh"'
            )
        if component_sources["start_mooncake_store.sh"] == _SCRIPT_FALLBACK_SOURCE:
            result.pre_serve.append(
                'bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_store.sh" &'
            )

    result.pre_serve.append(
        'echo "Mooncake distributed KV component sources: '
        f'mooncake.json={component_sources["mooncake.json"]}, '
        f'start_mooncake_store.sh={component_sources["start_mooncake_store.sh"]}, '
        f'env={component_sources["env"]}, transfer_config={component_sources["transfer_config"]}"'
    )
    result.pre_serve = list(dict.fromkeys(result.pre_serve))
    result.mooncake_component_sources = component_sources
    result.mooncake_script_assets_required = script_assets_required
    result.mooncake_master_section = _render_mooncake_master_section()
    return result


def _render_mooncake_master_section() -> list[str]:
    """合成 Mooncake master 分支段(early-exit 块的 shell 行)。

    master Pod 由环境变量 ``IS_MOONCAKE_MASTER`` 标记(TRUE/true/1/True),命中时
    只拉起 ``mooncake_master``、不执行 vllm serve / mooncake_client。该判别独立于
    下方 RANK_IP==MASTER_IP(vllm 推理侧 master/client),后者保持原样。

    段内命令由受控包代码合成(常量模板 + shlex.quote),不来自 YAML 任意 shell;
    master.env 由 script_builder 另行渲染落盘。
    """
    master_env_line = 'source "$SHARED_VOLUME_PATH/mooncake/master.env"'
    log_dir = "/var/log/wings"
    master_start = 'bash "$SHARED_VOLUME_PATH/mooncake/start_mooncake_master.sh"'
    return [
        "# ─── Mooncake master branch (IS_MOONCAKE_MASTER) ───",
        "# master Pod: 只拉起 mooncake_master, 不执行 vllm serve / mooncake_client。",
        "# 本判别独立于下方 RANK_IP==MASTER_IP (vllm 推理侧 master/client), 后者保持原样。",
        'export SHARED_VOLUME_PATH="${SHARED_VOLUME_PATH:-/shared-volume}"',
        'if [ "${IS_MOONCAKE_MASTER:-}" = "TRUE" ] || [ "${IS_MOONCAKE_MASTER:-}" = "true" ] || \\',
        '   [ "${IS_MOONCAKE_MASTER:-}" = "1" ] || [ "${IS_MOONCAKE_MASTER:-}" = "True" ]; then',
        f"    {master_env_line}",
        f"    mkdir -p {shlex.quote(log_dir)}",
        # 不做输出重定向:start_mooncake_master.sh 自带日志处理(log() 落
        # mooncake_master_setup.log,glog --log_dir);stdout/stderr 保持流向
        # start_command.sh 的 exec tee(engine.log / 容器 stdout),便于采集。
        f"    {master_start} &",
        "    MASTER_PID=$!",
        '    _wings_log INFO "mooncake master started, PID=$MASTER_PID"',
        '    wait "$MASTER_PID"',
        '    exit "$?"',
        "fi",
        "",
    ]
