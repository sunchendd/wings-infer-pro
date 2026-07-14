"""
KVOffload Expander — 智能 KV 卸载方案选择与渲染。

重要关键点:
- 三 scheme(cpu / disk / cpu_disk)三选一,按 (memory_offload_enabled, disk_offload_enabled)
  组合:(T,F)→cpu;(F,T)→disk;(T,T)→cpu_disk;(F,F)→None。不再深合并 cpu+disk。
- fallback:目标 scheme 缺失时,cpu_disk 缺 → 退化 disk > cpu > None;cpu/disk 缺 → None。
- cpu = vllm 原生 OffloadingConnector(无 lmcache 包 / 不落盘配置文件)。
- disk / cpu_disk = lmcache(LMCacheConnectorV1):需 lmcache 包 + lmcache_config.yaml
  (yaml 为容量真相源;env/cli 为补充)。cpu_disk 比 disk 多 local_cpu:true + max_local_cpu_size。
- 容量类占位符({mem_gb_to_blocks} 等)由 PlaceholderContext 解析;容量值由 yaml_loader 决定。
- 配置文件落盘:disk/cpu_disk 命中且有 files: 块时,由通用 render.write_scheme_files
  渲染(占位符 {qat_*} 经 ctx 填充;qat_enabled 用 effective = vllm 且 cfg.qat_enabled)写到
  SHARED_VOLUME_PATH/<name>。指向文件的 env(如 LMCACHE_CONFIG_FILE)由 scheme 的 envs: 字面量
  声明,不再代码注入。LMCACHE_QAT_ENABLED 是派生 env(随 qat 开关,仅 vllm effective-on),
  仍代码注入。非 disk 命中 / 无 files 块 → 跳过(仅 WARN,不阻塞启动)。

方案结构:
    - name:       cpu / disk / cpu_disk
    - packages:   pip 依赖(name:version);disk/cpu_disk 带 lmcache:v0.3.15
    - cli_params: 任意键值对(典型 kv_transfer_config: {...}),由 render 渲染
    - envs:       环境变量(支持 {memory_capacity_gb} / {mem_gb_to_blocks} 等占位符);
                  指向落盘文件的 env(如 LMCACHE_CONFIG_FILE)在此字面量声明
    - files:      要落盘的配置文件列表([{name, content}],通用语法;disk/cpu_disk 放 lmcache_config.yaml)
"""

import logging
from dataclasses import replace
from typing import Any, Dict, List, Optional

from wings_accel.render import (
    PlaceholderContext,
    extract_packages,
    fill_envs,
    render_engine_config,
    write_scheme_files,
)
from wings_accel.schemas import EngineParams, SmartKVCacheConfig, _FeatureOutput

logger = logging.getLogger(__name__)


def smart_kv_offload_expander(
    cfg: SmartKVCacheConfig,
    block: Any,
    ctx: PlaceholderContext,
    engine_name: str = "vllm",
) -> Optional[_FeatureOutput]:
    """智能 KV 卸载方案选择与渲染 —— 三 scheme(cpu/disk/cpu_disk)三选一。

    选择(由 cfg.memory_offload_enabled / disk_offload_enabled 组合):
      (mem, disk) = (T,F) → cpu;(F,T) → disk;(T,T) → cpu_disk;(F,F) → None。
    fallback:目标 scheme 缺失时,cpu_disk 缺 → 退化 disk > cpu > None;cpu/disk 缺 → None。

    cpu = vllm 原生 OffloadingConnector(无 lmcache 包 / 不落盘配置文件)。
    disk / cpu_disk = lmcache(LMCacheConnectorV1):需 lmcache 包 + lmcache_config.yaml
    (yaml 为容量真相源;env/cli 为补充)。cpu_disk 比 disk 多 local_cpu:true + max_local_cpu_size。
    QAT 正交:disk/cpu_disk 命中且有 files: 块 → 通用 write_scheme_files 落盘配置文件(如
    lmcache_config.yaml)+ 注入派生 env LMCACHE_QAT_ENABLED(随 qat 开关,effective = vllm 且
    cfg.qat_enabled);指向文件的 env(如 LMCACHE_CONFIG_FILE)由 scheme 的 envs: 声明。

    Args:
        cfg: KV cache 配置(memory_offload_enabled / disk_offload_enabled / qat_*)。
        block: kv_offload scheme 列表(cpu/disk/cpu_disk 各最多一项)。
        ctx: 占位符上下文。
        engine_name: 引擎名;仅 vllm 启用 QAT。

    Returns:
        _FeatureOutput(选中 scheme + 渲染后 EngineParams + packages);无可选 → None。
    """
    # 主开关关 / 未配置 / 非 list → None
    if not cfg.enabled or not isinstance(block, list) or not block:
        return None

    # name → scheme(cpu/disk/cpu_disk 各最多一项;重名取后者,与历史 last-write-wins 一致)
    schemes: Dict[str, Dict[str, Any]] = {
        str(s.get("name")): s
        for s in block
        if isinstance(s, dict) and s.get("name")
    }

    memory_on = bool(cfg.memory_offload_enabled)
    disk_on = bool(cfg.disk_offload_enabled)
    if not memory_on and not disk_on:
        return None

    # 三选一
    if memory_on and disk_on:
        target = "cpu_disk"
    elif disk_on:
        target = "disk"
    else:
        target = "cpu"

    # fallback:cpu_disk 缺 → disk > cpu > None;cpu/disk 缺 → None
    if target not in schemes:
        if target == "cpu_disk" and ("disk" in schemes or "cpu" in schemes):
            target = "disk" if "disk" in schemes else "cpu"
            logger.warning(
                "kv_offload: cpu_disk scheme 缺失,退化到 %r(yaml 需显式声明 cpu_disk 才能用组合)",
                target,
            )
        else:
            logger.warning("kv_offload: 目标 scheme %r 缺失,关闭 KV 卸载", target)
            return None

    selected = schemes[target]

    # 渲染选中 scheme 的 cli_params / envs(单 scheme,无需合并);envs 拷贝避免污染 yaml dict
    cli_params: Dict[str, Any] = selected.get("cli_params") or {}
    envs: Dict[str, Any] = dict(selected.get("envs") or {})
    packages: List[str] = extract_packages(selected)

    # disk/cpu_disk(lmcache)命中:scheme 的 files: 块统一落盘(lmcache_config.yaml 等),
    # 并注入派生 env LMCACHE_QAT_ENABLED(随 qat 开关;仅 vllm 视为 effective-on)。
    # LMCACHE_CONFIG_FILE 等指向文件的 env 由 scheme 的 envs: 字面量声明,不再代码注入。
    if target in ("disk", "cpu_disk"):
        files = selected.get("files") or []
        if files:
            effective_qat = bool(cfg.qat_enabled) and (engine_name or "").lower() == "vllm"
            render_ctx = replace(ctx, qat_enabled=effective_qat)
            write_scheme_files(files, render_ctx)
            envs["LMCACHE_QAT_ENABLED"] = "True" if effective_qat else "False"
        else:
            logger.warning(
                "kv_offload: disk 命中但 scheme 缺 files 块;跳过配置文件落盘"
                "(LMCACHE_QAT_ENABLED 不注入,容量参数可能不被 lmcache 识别)。"
            )

    engine_params = EngineParams(
        env=fill_envs(envs, ctx),
        engine_config=render_engine_config(cli_params, ctx),
    )
    return _FeatureOutput(
        scheme=str(selected.get("name", "")),
        engine_params=engine_params,
        packages=packages,
    )
