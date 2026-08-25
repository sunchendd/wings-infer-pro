"""wings-accel(resolve_smart_accel_from_config)接入适配器。

职责:把"智能加速"(投机解码 / KV 卸载 / KV 稀疏)
统一委托给 wings-accel 模块——wings-control **只忠实映射** MaaS 开关 + 上下文为 ``LoadFlags``、调用
``resolve_smart_accel_from_config`` 定位 smart-accel YAML 并解析,把返回的
``engine_params`` / scheme 收成 :class:`AccelResult` 供上层渲染。
**wings-control 自己不算任何加速参数**。

边界:wings-accel 模块**已合入本仓**(`src/wings_accel/`),batch1 已端到端验证
(`tests/integration/test_accel_enabled_e2e.py`)。本适配器仍对**模块缺失 / 无资产 / 异常**做
**guard 兜底**——任一情况 → 返回空 :class:`AccelResult`(accel 关闭,主流程零影响,no-op 安全)。

trace 说明:wings-accel 的 ``engine_params.engine_config`` 是结构化引擎参数且与 trace 体系解耦,
由 wings-control 统一渲染 argv;scheme 字段可写 audit。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from wings_ctl.utils.env_utils import parse_bool

logger = logging.getLogger(__name__)

# MaaS 页面下发口径补偿(GB):页面 bug 实际下发 = 节点总内存 − 5GB,正确契约应为总内存 − 20GB,
# 入口换算后统一再扣 15GB 恢复正确口径;页面修复(恢复 −20GB 下发)后删除本补偿。
_POD_MEM_MASS_SHORTFALL_GB = 15


@dataclass
class GeneratedFileSpec:
    """wings-accel 产出、由 wings-control 在产物阶段写入的文件计划。

    与 wings_accel.schemas.GeneratedFile 解耦的 wings-ctl 侧表示,避免对
    guard-import 的 wings_accel 包硬依赖;字段由 :func:`collect_output` 用 getattr 归一。

    Attributes:
        path: 容器内目标绝对路径(如 ``/shared-volume/lmcache_config.yaml``)。
        content: 已填解析期占位符的最终文本;``${VAR}`` 保持字面量,运行时由 pre-serve envsubst 展开。
        mode: 权限(如 ``"0644"``/``"0755"``);None = 用默认权限。
        scope: all/master/client(accel 内部已消费用于 pre-serve 分流,此处仅审计)。
        source_file: 溯源文件(可空,仅审计)。
        source_path: 溯源路径(可空,仅审计)。
    """

    path: str
    content: str
    mode: str | None = None
    scope: str = "all"
    source_file: str = ""
    source_path: str = ""


@dataclass
class AccelResult:
    """wings-accel 三类产出的扁平汇总,供 wings-control append 到 argv / env / audit。

    Attributes:
        engine_config: 追加到引擎配置的结构化参数(``engine_params.engine_config``)。
        env: 注入容器的环境变量(``engine_params.env``)。
        audit: 选中 scheme 元数据,仅写 audit.json。
        packages: 各选中 scheme 声明的 pip 依赖(``name:version`` 字符串);供 install 段 ``--config``。
        generated_files: 待写文件计划(解析期不落盘,由 script_builder 在产物阶段写入)。
        enabled: 是否真正调用了 wings-accel(模块在场且成功产出);False = no-op/降级。
    """

    engine_config: dict[str, Any] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)
    packages: list[str] = field(default_factory=list)
    enabled: bool = False
    # KV 内存卸载最终容量(GB,页面回显口径):auto 估算值或数值模式解析值;生效 → int,
    # auto 请求但估算不足被关 → 0,KV 卸载未请求 → None。供 script_builder 写
    # advanced_features.json 的 others.kv_mem_offload_size(health 接口 /v1/startup/accel 透出)。
    kv_mem_offload_size_gb: int | None = None
    # KV 磁盘卸载实际生效路径;disk 开启且 offload 产出 → str,否则 None。script_builder 在
    # vllm serve 前渲染残留清理(服务重启后旧 KV 落数据会超出 MaaS 规划容量)。
    kv_disk_offload_path: str | None = None
    # KV 存储后端(memcache/mooncake)pre-serve 命令:script_builder 在 vllm serve 前渲染。
    # pre_serve=所有节点(生成配置文件);pre_serve_master=仅 master 节点起 daemon;
    # pre_serve_client=仅 client 节点(非 master)。
    pre_serve: list[str] = field(default_factory=list)
    pre_serve_master: list[str] = field(default_factory=list)
    pre_serve_client: list[str] = field(default_factory=list)
    generated_files: list[GeneratedFileSpec] = field(default_factory=list)


def _import_accel():
    """guard-import wings-accel 模块。

    模块为顶层包 ``wings_accel``,非 ``wings_ctl.accel``(后者是本适配器自包)。

    Returns:
        模块对象(需含 ``resolve_smart_accel_from_config`` + ``LoadFlags``);缺失/不完整 → None
        (accel 关闭,主流程不受影响)。
    """
    try:
        import wings_accel as mod  # 顶层包:resolver + dataclasses + loader
    except Exception:  # pragma: no cover - 取决于模块是否合入
        return None
    return mod if hasattr(mod, "resolve_smart_accel_from_config") else None


def _as_bool(env: dict, key: str) -> bool:
    """MaaS env dict 里 key 的值解析为布尔;缺失/空/非法 → False。

    统一走 :func:`env_utils.parse_bool`(真值集合 ``{1,true,yes,y,on}``),
    修复旧实现只认 ``"true"`` 导致 ``ENABLE_XXX=1/yes/on`` 不生效的问题。

    Args:
        env: MaaS 下发的环境变量字典。
        key: 待解析的开关键(如 ``ENABLE_SPARSE``)。

    Returns:
        真值集合命中 → ``True``;缺失/空串/非法 → ``False``。
    """
    value = env.get(key)
    return parse_bool(value if value is None else str(value), default=False)


def _as_int(value: Any) -> int:
    """容量类 env 转 int;空/非法 → 0(不抛,容错)。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _pod_mem_mib_to_gb(value: Any) -> int:
    """AVAILABLE_POD_MEM_SIZE 由 MaaS 以 MiB 下发(如 65536 表示 64GB),转成 GB int。

    与老仓库 resolve_offload_cpu_capacity_gb 对齐:float(mib)/1024 后向下取整;
    空/非法 → 0(关闭 auto 估算,避免误判)。

    MaaS 下发口径补偿:页面 bug 实际下发 = 节点总内存 − 5GB,而正确契约应为总内存 − 20GB,
    故换算后再扣 15GB 恢复正确口径(页面修复后移除)。
    """
    try:
        gb = int(int(value) // 1024)
    except (TypeError, ValueError):
        return 0
    return max(0, gb - _POD_MEM_MASS_SHORTFALL_GB)


def _kv_mem_size(value: Any) -> str:
    """KV_MEM_OFFLOAD_SIZE 原样归一:auto / 数值 GB / 空。"""
    raw = str(value or "").strip().lower()
    if raw in ("", "false", "0", "no", "off"):
        return ""
    if raw == "auto":
        return "auto"
    return raw if _as_int(raw) > 0 else ""


def collect_accel_switches(env: dict) -> dict[str, Any]:
    """收口读取 MaaS smart/accel ENV 开关(v3 命名)→ 归一字典(单一真相源)。"""
    memory_size_mode = _kv_mem_size(env.get("KV_MEM_OFFLOAD_SIZE") or env.get("ENABLE_KV_MEM_OFFLOAD"))
    mem_enabled = _as_bool(env, "ENABLE_KV_MEM_OFFLOAD") or bool(memory_size_mode)
    return {
        # 投机解码;草稿路径原样透传,none/null 字面量的归一在消费点(wings_accel/decoders._eligible)做
        "speculative_enabled": _as_bool(env, "ENABLE_SPECULATIVE_DECODE"),
        "speculative_model_path": env.get("SPECULATIVE_DECODE_MODEL_PATH") or "",
        # KV 稀疏
        "sparse_enabled": _as_bool(env, "ENABLE_SPARSE"),
        "sparse_level": env.get("SPARSE_LEVEL", "performance_first") or "performance_first",
        # KV 卸载(一级 → 二级 mem/disk → 三级 qat)
        "kv_offload_enabled": _as_bool(env, "ENABLE_KV_OFFLOAD") or mem_enabled,
        "kv_mem_enabled": mem_enabled,
        "kv_mem_size_mode": memory_size_mode,
        "kv_mem_size_gb": 0 if memory_size_mode in ("", "auto") else _as_int(memory_size_mode),
        "kv_disk_enabled": _as_bool(env, "ENABLE_KV_DISK_OFFLOAD"),
        "kv_disk_path": env.get("KV_DISK_OFFLOAD_PATH", "") or "",
        "kv_disk_size_gb": _as_int(env.get("KV_DISK_OFFLOAD_SIZE")),
        "kv_qat_enabled": _as_bool(env, "ENABLE_KV_QAT"),
        "kv_qat_compress_level": _as_int(env.get("KV_QAT_COMPRESS_LEVEL")),
        "kv_qat_instance_num": _as_int(env.get("KV_QAT_INSTANCE_NUM")),
        "available_pod_mem_gb": _pod_mem_mib_to_gb(env.get("AVAILABLE_POD_MEM_SIZE")),
        # PD_ROLE 透传(env_utils 已校验);decoders/offload 内部按需自取。
        "pd_role": env.get("PD_ROLE") or None,
        # KV 存储后端(memcache/mooncake)由 yaml 声明、按 connector 内容路由;不再有 KV_STORE_* env。
        # 注:topology 不再在此从 env 推导(原 _resolve_topology 滥用 PD_ROLE/DISTRIBUTED/NODE_IPS,
        # 且 PD_ROLE 与上方重复读)。topology 由上层 config_resolver 传入 apply_smart_accel。
    }


def active_accel_switch_names(env: dict) -> list[str]:
    """返回当前生效的 accel 开关名，用于引擎能力门控日志。"""
    switches = collect_accel_switches(env)
    names: list[str] = []
    if switches["speculative_enabled"]:
        names.append("ENABLE_SPECULATIVE_DECODE")
    if switches["sparse_enabled"]:
        names.append("ENABLE_SPARSE")
    if _as_bool(env, "ENABLE_KV_OFFLOAD"):
        names.append("ENABLE_KV_OFFLOAD")
    if switches["kv_mem_enabled"]:
        names.append("ENABLE_KV_MEM_OFFLOAD")
    if switches["kv_disk_enabled"]:
        names.append("ENABLE_KV_DISK_OFFLOAD")
    if switches["kv_qat_enabled"]:
        names.append("ENABLE_KV_QAT")
    return names


def build_smart_input(mod, *, hardware_family: str, gpu_count: int | None, model_path: str | None,
                      model_name: str | None, engine: str, engine_version: str | None,
                      switches: dict):
    """兼容旧单测/旧调用:构造 SmartAccelInput;生产路径不使用本函数。"""
    system_config_cls = mod.SystemConfig if hasattr(mod, "SystemConfig") else mod.HardwareConfig

    return mod.SmartAccelInput(
        hardware_config=system_config_cls(
            gpu_type=hardware_family,
            gpu_count=gpu_count or 1,
            pod_available_memory_gb=switches["available_pod_mem_gb"],
        ),
        model_config=mod.ModelConfig(model_path=model_path or "", model_name=model_name),
        engine_config=mod.EngineConfig(name=engine, version=engine_version or ""),
        deployment_mode=mod.DeploymentMode(pd_role=switches["pd_role"]),
        smart_decoding_config=mod.SmartDecodingConfig(
            enabled=switches["speculative_enabled"],
            model_path=switches["speculative_model_path"],
        ),
        smart_kv_cache_config=mod.SmartKVCacheConfig(
            enabled=switches["kv_offload_enabled"],
            memory_offload_enabled=switches["kv_mem_enabled"],
            memory_offload_size_mode=switches["kv_mem_size_mode"],
            disk_offload_enabled=switches["kv_disk_enabled"],
            disk_capacity_gb=switches["kv_disk_size_gb"],
            disk_path=switches["kv_disk_path"],
            qat_enabled=switches["kv_qat_enabled"],
            qat_device_count=switches["kv_qat_instance_num"],
            qat_compression_level=switches["kv_qat_compress_level"],
        ),
        smart_kv_sparse_config=mod.SmartKVSparseConfig(
            enabled=switches["sparse_enabled"],
            mode=switches["sparse_level"],
        ),
        smart_accel={},  # 兼容旧单测/调用;生产路径走 resolve_smart_accel_from_config 加载 YAML
    )


def _collect_generated_files(raw_files: list) -> list[GeneratedFileSpec]:
    """把 wings-accel 输出的文件计划归一为 :class:`GeneratedFileSpec` 列表。

    逐项 getattr 读取,避免对 ``wings_accel.schemas.GeneratedFile`` 的字段结构硬依赖
    (accel 侧增删字段时本适配层不崩)。非文件条目(缺 path)跳过,保持输入顺序。

    Args:
        raw_files: ``output.generated_files`` 的原始列表(可能含无 path 的条目)。

    Returns:
        归一后的 :class:`GeneratedFileSpec` 列表;空/缺字段 → 对应默认值。
    """
    specs: list[GeneratedFileSpec] = []
    for raw in raw_files or []:
        path = str(getattr(raw, "path", "") or "").strip()
        if not path:
            continue
        specs.append(GeneratedFileSpec(
            path=path,
            content=str(getattr(raw, "content", "") or ""),
            mode=getattr(raw, "mode", None),
            scope=str(getattr(raw, "scope", "all") or "all"),
            source_file=str(getattr(raw, "source_file", "") or ""),
            source_path=str(getattr(raw, "source_path", "") or ""),
        ))
    return specs


def collect_output(output) -> AccelResult:
    """把 wings-accel 输出汇总成 :class:`AccelResult`。"""
    engine_params = getattr(output, "engine_params", None)
    if engine_params is not None:
        engine_config = dict(getattr(engine_params, "engine_config", {}) or {})
        env = dict(getattr(engine_params, "env", {}) or {})
        packages = list(getattr(output, "packages", []) or [])
        pre_serve = list(getattr(output, "pre_serve", []) or [])
        pre_serve_master = list(getattr(output, "pre_serve_master", []) or [])
        pre_serve_client = list(getattr(output, "pre_serve_client", []) or [])
        generated_files = _collect_generated_files(
            getattr(output, "generated_files", None) or []
        )
        scheme_fields = {
            "smart_decoding_scheme": getattr(output, "smart_decoding_scheme", None),
            "smart_kv_sparse_scheme": getattr(output, "smart_kv_sparse_scheme", None),
            "smart_kv_cache_scheme": getattr(output, "smart_kv_cache_scheme", None),
        }
        audit = {key: value for key, value in scheme_fields.items() if value is not None}
        diagnostics = dict(getattr(output, "diagnostics", {}) or {})
        if diagnostics:
            audit["diagnostics"] = diagnostics
        return AccelResult(
            engine_config=engine_config,
            env=env,
            # 裸内容(scheme dict);由 emitter 统一包成 audit["wings_accel"](勿在此预包,否则双层嵌套)
            audit=audit,
            # 选中 scheme 声明的 pip 依赖;getattr 兜底旧/stub 输出无该字段 → []
            packages=packages,
            # KV 存储后端 pre-serve 命令;getattr 兜底旧/stub 输出无该字段 → []
            pre_serve=pre_serve,
            pre_serve_master=pre_serve_master,
            pre_serve_client=pre_serve_client,
            # KV 内存卸载页面回显容量(auto 估算/数值 GB);getattr 兜底旧/stub 输出无该字段 → None
            kv_mem_offload_size_gb=getattr(output, "kv_mem_offload_size_gb", None),
            # KV 磁盘卸载路径(disk 开启且产出);getattr 兜底旧/stub 输出无该字段 → None
            kv_disk_offload_path=getattr(output, "kv_disk_offload_path", None),
            # 待写文件计划;getattr 兜底旧/stub 输出无该字段 → []。逐项用 getattr 归一,避免硬依赖
            # wings_accel.GeneratedFile 的具体结构(两侧可独立演进)。
            generated_files=generated_files,
            # 任一运行时产出均表示 accel 已生效。文件计划、依赖和 pre-serve 不能因
            # engine_config/env 为空而漏掉安装或启动准备阶段。
            enabled=bool(
                engine_config
                or env
                or packages
                or pre_serve
                or pre_serve_master
                or pre_serve_client
                or generated_files
            ),
        )

    engine_config: dict[str, Any] = {}
    env: dict[str, str] = {}
    audit: dict[str, Any] = {}
    for name in ("smart_decoding_output", "smart_kv_cache_output", "smart_kv_sparse_output"):
        part = getattr(output, name, None)
        if part is None:
            continue
        engine_config.update(dict(getattr(part, "engine_config", {}) or {}))
        env.update(dict(getattr(part, "env", {}) or {}))
        diag = dict(getattr(part, "wings_accel_params", {}) or {})
        if diag:
            audit[name] = diag
    top = dict(getattr(output, "wings_accel_params", {}) or {})
    if top:
        audit["wings_accel"] = top
    return AccelResult(
        engine_config=engine_config, env=env, audit=audit,
        enabled=bool(engine_config or env),
        kv_mem_offload_size_gb=getattr(output, "kv_mem_offload_size_gb", None),
        kv_disk_offload_path=getattr(output, "kv_disk_offload_path", None),
    )


def apply_smart_accel(*, hardware_family: str, gpu_count: int | None, model_path: str | None,
                      model_name: str | None, engine: str, engine_version: str | None,
                      config_root: str = "", pd_role: str | None = None,
                      topology: str | None = None,
                      tp_size: int = 0, dp_size: int = 0,
                      enabled: bool = True,
                      env: dict | None = None) -> AccelResult:
    """委托 wings-accel 生成加速产出;模块缺失/异常 → 空 :class:`AccelResult`(不打断启动)。

    topology 由上层 ``config_resolver`` 传入(已聚合 PD_ROLE/DISTRIBUTED/NODE_IPS,
    对齐 wings-control ``Topology`` 枚举值);本适配层不再从 env 推导拓扑。

    tp_size/dp_size 由调用方从 model recipe 的 scenarios.engine_config 透传,供 KV 内存
    auto 估算 worker_count;smart-accel YAML 常无 scenarios 字段,故需上游注入。0 = 未下发。
    """
    if not enabled:
        return AccelResult()
    mod = _import_accel()
    if mod is None:
        logger.debug("wings-accel module is unavailable; skipping smart acceleration delegation")
        return AccelResult()
    resolved_env = os.environ if env is None else env
    try:
        switches = collect_accel_switches(resolved_env)
        if pd_role is not None:
            # 调用方显式覆盖 pd_role;topology 不再在此重算,
            # 由上层 config_resolver 一并负责(它已能根据 PD_ROLE 推导 Topology)。
            switches["pd_role"] = pd_role

        # MaaS 开关为唯一驱动(框架已无 auto 机制):kv/sparse/decoding 是否启用 100% 由
        # switches 决定,smart_accel YAML 仅作全量占位模板,块存在不再自动启用任何特性。
        # 全关 → 全 no-op,由 tests/integration/test_accel_enabled_e2e.py::test_accel_disabled_is_no_op 守。
        flags = mod.LoadFlags(
            kv=switches["kv_offload_enabled"],
            sparse=switches["sparse_enabled"],
            disk=switches["kv_disk_enabled"],
            qat=switches["kv_qat_enabled"],
            disk_gb=switches["kv_disk_size_gb"],
            disk_path=switches["kv_disk_path"],
            qat_devices=switches["kv_qat_instance_num"],
            qat_level=switches["kv_qat_compress_level"],
            decoding_enabled=switches["speculative_enabled"],
            decoding_model_path=switches["speculative_model_path"],
            sparse_level=switches["sparse_level"],
            pd_role=switches["pd_role"],
            topology=topology,
            memory_offload_size_mode=switches["kv_mem_size_mode"],
            pod_available_memory_gb=switches["available_pod_mem_gb"],
            tp_size=tp_size,
            dp_size=dp_size,
        )
        output = mod.resolve_smart_accel_from_config(
            config_root=config_root,
            engine=engine,
            engine_version=engine_version or "",
            hardware_family=hardware_family,
            model_name=model_name or model_path or "",
            flags=flags,
            gpu_count=gpu_count or 1,
        )
        if output is None:
            return AccelResult()
        result = collect_output(output)
        logger.info(
            "wings-accel applied: +%d engine_config / +%d env / audit=%s",
            len(result.engine_config), len(result.env), list(result.audit),
        )
        return result
    except Exception as exc:  # 加速委托失败不应打断主流程 → 降级为不加速
        logger.warning("wings-accel invocation failed; continuing without acceleration: %s", exc)
        return AccelResult()
