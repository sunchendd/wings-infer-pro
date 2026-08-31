"""
SmartAccel 总入口 — func_smart_accel() 主流水线。

重要关键点:
- func_smart_accel 是唯一主流水线,只消费 SmartAccelInput,不直接读取 YAML/环境变量。
- 输入检查层只写日志,不会阻断输出或污染 SmartAccelOutput。
- engine=sglang 直接返回空 scheme + 空 EngineParams。
- decoding/sparse/kv_offload 各自独立展开;custom_features 只有在前三者至少一项产出后才启用。
- 保留冲突仲裁扩展点;当前无硬编码冲突规则。

编排步骤:
1. collect_smart_accel_warnings: 输入检查,仅写日志
2. sglang 短路:engine 为 sglang → 全 None(sglang 暂不支持 smart accel)
3. 从 smart_input.smart_accel 取出各特性块,构建 PlaceholderContext
4. 运行 decoding / sparse / kv_offload expander,各返回 _FeatureOutput
5. resolve_conflicts:冲突扩展点(当前 no-op)
6. 条件运行 custom_features expander
7. 组装 SmartAccelOutput(选中 scheme + 合并后的 EngineParams)

外部集成:
- smart_input: 由 yaml_loader 从 model.yaml 构造,聚合系统/模型/引擎/部署上下文 +
  用户意图开关 + smart_accel 模板块(解码方案/卸载介质/稀疏方案/自定义特性)。
- func_smart_accel 只接受 smart_input 一个参数。
"""

import logging
from typing import Optional

from wings_accel.conflict import resolve_conflicts
from wings_accel.custom import smart_custom_features_expander
from wings_accel.decoders import _normalize_optional_path, smart_decoding_expander
from wings_accel.offload import smart_kv_offload_expander
from wings_accel.render import PlaceholderContext, merge_engine_params
from wings_accel.schemas import (
    EngineParams,
    GeneratedFile,
    PackageRequirement,
    SmartAccelInput,
    SmartAccelOutput,
    SmartAccelPackageConflictError,
)
from wings_accel.sparse import smart_sparse_expander
from wings_accel.validators import collect_smart_accel_warnings

logger = logging.getLogger(__name__)


def _ensure_unique_generated_file_paths(files: list[GeneratedFile]) -> None:
    """Reject ambiguous generated-file plans before they reach wings-control."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for generated_file in files:
        if generated_file.path in seen:
            duplicates.append(generated_file.path)
        else:
            seen.add(generated_file.path)
    if duplicates:
        paths = ", ".join(dict.fromkeys(duplicates))
        raise ValueError(f"SmartAccel generated file paths must be unique: {paths}")


def _merge_package_requirements(
    requirements: list[tuple[str, PackageRequirement]],
) -> list[str]:
    """按规范化包名汇总精确版本；同包不同版本必须显式失败。"""
    selected: dict[str, tuple[str, PackageRequirement]] = {}
    for feature_name, requirement in requirements:
        existing = selected.get(requirement.canonical_name)
        if existing is None:
            selected[requirement.canonical_name] = (feature_name, requirement)
            continue
        existing_feature, existing_requirement = existing
        # 冲突比较用规范化版本(PEP 440):v0.4.5 与 0.4.5 视为同一版本,不算冲突;
        # 交付仍取 YAML 首次声明的原始 name:version(manifest)。
        if existing_requirement.canonical_version != requirement.canonical_version:
            raise SmartAccelPackageConflictError(
                "SmartAccel package conflict for "
                f"{requirement.canonical_name}: {existing_requirement.manifest} "
                f"from feature={existing_feature} conflicts with "
                f"{requirement.manifest} from feature={feature_name}"
            )
    return [requirement.manifest for _, requirement in selected.values()]


def func_smart_accel(smart_input: SmartAccelInput) -> SmartAccelOutput:
    """Main entry point for SmartAccel feature resolution.

    Args:
        smart_input: User intent (feature switches) + system/model/engine context +
            smart_accel block (decoding / kv_offload / sparse / custom_features)
            read from model.yaml.

    Returns:
        SmartAccelOutput with selected schemes + merged EngineParams.
        sglang → empty schemes and empty EngineParams.
    """
    # Step 1: input warnings(log-only)
    for warning in collect_smart_accel_warnings(smart_input):
        logger.warning("SmartAccel input warning: %s", warning)

    # Step 2: sglang 短路 → 全 None
    if (smart_input.engine_config.name or "").lower() == "sglang":
        logger.info("SmartAccel: sglang engine → all features disabled (no-op)")
        return SmartAccelOutput()

    # Step 3: smart_accel 模板块 + 占位符上下文
    smart_accel = smart_input.smart_accel or {}
    ctx = _build_placeholder_context(smart_input)

    # Step 4: run expanders
    # smart_accel 已在 yaml_loader 按 topology 路由出扁平子块(scenario 嵌套结构,见 smart-yaml.md §1),
    # expander 直接消费 decoding/kv_offload/sparse,不再感知 scenario / topology。
    # PD prefill 节点不做投机(loader 路由剥 decoding 键的意图)——
    # topology/pd_role 为 prefill 侧时直接不产出 decoding。
    _topology = (smart_input.deployment_mode.topology or "").lower()
    _pd_role = (smart_input.deployment_mode.pd_role or "").lower()
    if "prefill" in _topology or _pd_role in ("prefill", "p"):
        decoding = None
    else:
        decoding = smart_decoding_expander(
            smart_input.smart_decoding_config,
            smart_input.model_config,
            smart_accel.get("decoding"),
            ctx,
        )
    sparse = smart_sparse_expander(
        smart_input.smart_kv_sparse_config,
        smart_accel.get("sparse"),
        ctx,
    )
    offload = smart_kv_offload_expander(
        smart_input.smart_kv_cache_config,
        smart_accel.get("kv_offload"),
        ctx,
        engine_name=smart_input.engine_config.name,
    )

    # Step 5: conflict resolution extension point(currently no-op)
    decoding, sparse, offload, _ = resolve_conflicts(
        decoding,
        sparse,
        offload,
        smart_accel.get("decoding"),
        ctx,
    )

    # custom_features:仅当 decoding/kv_cache/sparse 至少一项产出时才启用
    custom = None
    if decoding or sparse or offload:
        custom = smart_custom_features_expander(smart_accel.get("custom_features"), ctx)

    # Step 6: assemble output
    engine_params = EngineParams()
    package_requirements: list[tuple[str, PackageRequirement]] = []
    pre_serve: list = []
    pre_serve_master: list = []
    pre_serve_client: list = []
    generated_files: list[GeneratedFile] = []
    for feature_name, feature in (
        ("decoding", decoding),
        ("kv_offload", offload),
        ("sparse", sparse),
        ("custom_features", custom),
    ):
        if feature:
            engine_params = merge_engine_params(engine_params, feature.engine_params)
            package_requirements.extend((feature_name, requirement) for requirement in feature.packages)
            pre_serve.extend(feature.pre_serve)
            pre_serve_master.extend(feature.pre_serve_master)
            pre_serve_client.extend(feature.pre_serve_client)
            generated_files.extend(feature.generated_files)
    _ensure_unique_generated_file_paths(generated_files)
    # 去重保序:同一依赖/命令被多个特性声明时只取一次
    packages = _merge_package_requirements(package_requirements)
    pre_serve = list(dict.fromkeys(pre_serve))
    pre_serve_master = list(dict.fromkeys(pre_serve_master))
    pre_serve_client = list(dict.fromkeys(pre_serve_client))

    diagnostics = _collect_diagnostics(
        {"decoding": decoding, "kv_cache": offload, "sparse": sparse},
    )

    return SmartAccelOutput(
        smart_decoding_scheme=decoding.scheme if decoding else None,
        smart_kv_cache_scheme=offload.scheme if offload else None,
        smart_kv_sparse_scheme=sparse.scheme if sparse else None,
        engine_params=engine_params,
        kv_mem_offload_size_gb=_resolve_kv_mem_offload_size_gb(smart_input.smart_kv_cache_config),
        kv_disk_offload_path=_resolve_kv_disk_offload_path(smart_input.smart_kv_cache_config, offload),
        diagnostics=diagnostics,
        packages=packages,
        pre_serve=pre_serve,
        pre_serve_master=pre_serve_master,
        pre_serve_client=pre_serve_client,
        generated_files=generated_files,
    )


def _collect_diagnostics(features) -> dict:
    """收集各特性降级诊断,只保留 degraded=True 的项。

    Args:
        features: feature 名到 _FeatureOutput/None 的映射;key 会原样成为 diagnostics 的 feature 名。

    Returns:
        diagnostics 字典;未降级特性不出现,降级特性包含 degraded 与 degrade_reason。

    Raises:
        无。纯数据汇总函数,不主动抛异常。
    """
    diagnostics = {}
    for name, feature in features.items():
        if feature and feature.degraded:
            diagnostics[name] = {
                "degraded": True,
                "degrade_reason": feature.degrade_reason,
            }
    return diagnostics


def _memory_capacity_gb(kv) -> int:
    """返回内部渲染用 CPU 卸载容量 GB。"""
    if hasattr(kv, "_memory_capacity_gb"):
        return int(getattr(kv, "_memory_capacity_gb") or 0)
    raw = str(getattr(kv, "memory_offload_size_mode", "") or "").strip().lower()
    if raw in ("", "auto", "false", "0", "no", "off"):
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def _resolve_kv_mem_offload_size_gb(kv) -> Optional[int]:
    """推导 KV 内存卸载页面回显容量(GB)。

    语义对齐老仓库 resolve_effective_kv_mem_offload_size 的页面口径:
      - KV 卸载一级关 / 仅磁盘 → None(当前场景无有效容量);
      - 请求过内存卸载(auto/数值)但未生效(auto 估算不足 / YAML 无内存方法)→ 0
        (推荐结果低于生效下限);
      - 内存卸载生效 → 渲染容量(loader 已解析:auto=估算值 / 数值=固定 GB)。
    """
    if not getattr(kv, "enabled", False):
        return None
    if not getattr(kv, "memory_offload_enabled", False):
        mode = str(getattr(kv, "memory_offload_size_mode", "") or "").strip().lower()
        return 0 if mode else None
    capacity = _memory_capacity_gb(kv)
    return capacity if capacity > 0 else 0


def _resolve_kv_disk_offload_path(kv, offload) -> Optional[str]:
    """推导 KV 磁盘卸载实际生效路径(None = 无磁盘卸载,不需要清理)。

    条件:disk_offload_enabled 且 kv_offload 特性真产出(offload 非 None;backend scheme
    命中等无 disk 的场景 offload 可能因方案路由不带 disk,此时 scheme envs 无 LMCACHE_LOCAL_DISK,
    不该清理)。路径取 SmartKVCacheConfig.disk_path(loader 已解析自 KV_DISK_OFFLOAD_PATH)。
    """
    if offload is None or not getattr(kv, "disk_offload_enabled", False):
        return None
    path = str(getattr(kv, "disk_path", "") or "").strip()
    return path or None


def _build_placeholder_context(smart_input: SmartAccelInput) -> PlaceholderContext:
    """从 SmartAccelInput 各子配置派生占位符上下文。"""
    kv = smart_input.smart_kv_cache_config
    # 端口与协议由 YAML 资产明文声明(不再代码写死);IP 经 {rank_ip}/{master_ip} → ${VAR}
    # 由运行时 envsubst 展开。KV 工具选择由 yaml 声明 + offload 按 connector 内容路由。
    return PlaceholderContext(
        memory_capacity_gb=_memory_capacity_gb(kv),
        memory_offload_enabled=kv.memory_offload_enabled,
        disk_capacity_gb=kv.disk_capacity_gb,
        disk_offload_enabled=kv.disk_offload_enabled,
        disk_path=kv.disk_path,
        qat_enabled=kv.qat_enabled,
        qat_device_count=kv.qat_device_count,
        qat_compression_level=kv.qat_compression_level,
        # 归一(none/null 字面量→空、strip 空格):防字面量/带空格路径被 $path 渲染进 config
        draft_model_path=_normalize_optional_path(smart_input.smart_decoding_config.model_path),
        gpu_count=smart_input.hardware_config.gpu_count,
        tp_size=kv.tp_size,
        dp_size=kv.dp_size,
        config_root=smart_input.config_root,
        source_file=smart_input.source_file,
        source_path=smart_input.source_path,
    )
