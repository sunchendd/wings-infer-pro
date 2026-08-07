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
from wings_accel.conflict import resolve_conflicts
from wings_accel.custom import smart_custom_features_expander
from wings_accel.decoders import smart_decoding_expander
from wings_accel.offload import smart_kv_offload_expander
from wings_accel.render import PlaceholderContext, merge_engine_params
from wings_accel.schemas import EngineParams, SmartAccelInput, SmartAccelOutput
from wings_accel.sparse import smart_sparse_expander
from wings_accel.validators import collect_smart_accel_warnings

logger = logging.getLogger(__name__)


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
        decoding, sparse, offload, smart_accel.get("decoding"), ctx,
    )

    # custom_features:仅当 decoding/kv_cache/sparse 至少一项产出时才启用
    custom = None
    if decoding or sparse or offload:
        custom = smart_custom_features_expander(smart_accel.get("custom_features"), ctx)

    # Step 6: assemble output
    engine_params = EngineParams()
    packages: list = []
    pre_serve: list = []
    pre_serve_master: list = []
    pre_serve_client: list = []
    for feature in (decoding, offload, sparse, custom):
        if feature:
            engine_params = merge_engine_params(engine_params, feature.engine_params)
            packages.extend(feature.packages)
            pre_serve.extend(feature.pre_serve)
            pre_serve_master.extend(feature.pre_serve_master)
            pre_serve_client.extend(feature.pre_serve_client)
    # 去重保序:同一依赖/命令被多个特性声明时只取一次
    packages = list(dict.fromkeys(packages))
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
        diagnostics=diagnostics,
        packages=packages,
        pre_serve=pre_serve,
        pre_serve_master=pre_serve_master,
        pre_serve_client=pre_serve_client,
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
        draft_model_path=smart_input.smart_decoding_config.model_path,
        gpu_count=smart_input.hardware_config.gpu_count,
        tp_size=kv.tp_size,
        config_root=smart_input.config_root,
    )
