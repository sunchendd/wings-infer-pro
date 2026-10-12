"""
YAML 加载器 — 从模型 YAML 构建 SmartAccelInput。

解析以下标签:
- model: 模型元数据(model_id / name / architecture)
- hardware_profile: 硬件配置(gpu_type / gpu_count)
- smart_accel: smart_accel 块本体(scenario 嵌套结构,按 topology 路由出对应子块后嵌入
  SmartAccelInput.smart_accel 供 func_smart_accel 展开;详见 smart-yaml.md §1)
- scenarios.{topology}.strategies.{name}.engine_config: 引擎配置(读取 name/version/TP/DP,可选)

重要关键点:
- smart_accel 精确取自命中的模型 YAML,不合并 default_model.yaml。
- smart_accel 按 topology 路由(standalone/multi_node/pd_disaggregation.{prefill,decode});
  路由后的扁平子块嵌入 SmartAccelInput.smart_accel,expander 不感知 scenario。
- 自动探测只根据路由后子块决定默认开关;CLI/LoadFlags 可覆盖用户意图。
- KV offload 介质用 kv_offload[].name == cpu/disk 探测;主开关开但无介质时不兜底。
- 找不到 YAML 返回 None,由 api.resolve_smart_accel_from_config 调用方按 no-op 处理。
- config_root/smart-accel 优先,否则回落到随包分发的 smart-accel 配置。

智能内存分配(memory_offload_size_mode):
- auto: 从 scenarios engine_config 读取 TP/DP,结合 pod_available_memory_gb 估算 CPU 卸载容量。
- auto 估算低于 min_offload_threshold_gb 时默认关闭 memory_offload;显式开启则保留用户意图。
- 数值字符串:按 GB 固定配置。
- 分布式 KV 卸载(distributed_kv)复用同一估算:ENABLE_DISTRIBUTED_KV_OFFLOAD=true 且
  KV_MEM_OFFLOAD_SIZE=auto 时,memory_capacity_gb 填估算值(供脚本兜底 client.env 注入);
  估算不足同样关 memory_offload,由 distributed_offload expander 优雅降级。
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from wings_accel.memory_estimator import estimate_offload_memory
from wings_accel.schemas import (
    DeploymentMode,
    DistributedKVCacheConfig,
    EngineConfig,
    ModelConfig,
    SmartAccelInput,
    SmartDecodingConfig,
    SmartKVCacheConfig,
    SmartKVSparseConfig,
    SystemConfig,
)

logger = logging.getLogger(__name__)

# 提取运行时传入版本的"开头版本号段"(基础版本 + 可选渠道),用于归一化构建元数据。
# 只看开头,任何分隔符(- + _ . ~ 空白)之后的内容(cu130/时间戳/架构等)一律当构建元数据丢弃。
# 示例:
#   v0.21.0rc1-20260709144216 → base=0.21.0 + channel=rc1
#   v0.23.0-cu130-...         → base=0.23.0 + channel=""
#   v0.26.0_cu130_..._x86_64  → base=0.26.0 + channel=""
# 基础版本 = (\d+\.\d+\.\d+);渠道段 = ([A-Za-z]+\d*) 且必须紧贴基础版本(字母开头),
# 渠道段遇到分隔符立即停止(防 "0.23.0-cu130" 错把 cu130 当渠道)。
_SMART_ACCEL_VERSION_HEAD_RE = re.compile(
    r"^v?(\d+\.\d+\.\d+)([A-Za-z]+\d*)?"
)


def _candidate_version_dirs(engine_version: str) -> list[str]:
    """把传入的版本号展开成候选目录名列表(带 v 前缀),按精确优先排序。

    策略:**正则提取开头的版本号段**,不依赖后续分隔符是什么。任何 `- + _ . ~` 之类
    的分隔符和构建元数据(cu130、时间戳、架构标识等)都被一并丢弃,只保留基础版本(+ 渠道)。

    - "0.23.0"                                → ["v0.23.0"]
    - "v0.21.0rc"                             → ["v0.21.0rc"]
    - "v0.21.0rc1-20260709144216"             → ["v0.21.0rc1-20260709144216", "v0.21.0rc1", "v0.21.0rc"]
    - "v0.23.0-cu130-20260727055844"          → ["v0.23.0-cu130-20260727055844", "v0.23.0"]
    - "v0.26.0_cu130_202608091354_x86_64"     → ["v0.26.0_cu130_202608091354_x86_64", "v0.26.0"]

    优先级:原样(精确)→ 基础版本(剥所有构建元数据)→ 渠道归一化(rc1→rc)。
    """
    raw = str(engine_version).strip()
    if not raw:
        return []
    version_dir_name = raw if raw.startswith("v") else f"v{raw}"
    candidates = [version_dir_name]
    # 正则提取开头版本号段:v?(\d+\.\d+\.\d+) 抓基础版本(0.26.0 的 . 在 \d+ 之间,
    # 不会被当作分隔符,基础版本完整保留);后面可选的 ([A-Za-z]+\d*)? 抓渠道段(rc1、m),
    # 必须字母开头、紧贴基础版本。
    # 一旦遇到非字母数字字符(_ - + . ~ 空白等),正则立即停止 —— 后面的内容
    # (cu130/时间戳/架构标识等)全部当作构建元数据丢弃,不参与目录名拼接。
    # 命中 → 拿"基础版本 + 渠道"拼出基础目录名(如 v0.26.0、v0.21.0rc1)。
    m = _SMART_ACCEL_VERSION_HEAD_RE.match(raw)
    if m:
        base_with_v = f"v{m.group(1)}{m.group(2) or ''}"
        if base_with_v != version_dir_name:
            candidates.append(base_with_v)
        # 渠道归一化:rc1 → rc(配置目录用渠道形式)。
        if m.group(2):
            normalized = f"v{m.group(1)}{re.match(r'[A-Za-z]+', m.group(2)).group(0)}"
            if normalized != version_dir_name and normalized not in candidates:
                candidates.append(normalized)
    return candidates


def _scan_prefix_version_dir(engine_root: Path, engine_version: str) -> Optional[str]:
    """按引擎侧 version_resolver 的语义扫描版本目录(自定义版本号的兜底)。

    非数字版本号(如 kimi-k3、kimi-k3-a3)无法用 _candidate_version_dirs 句法展开
    (它只会补 v 前缀,得到 vkimi-k3 之类的空候选),这里改为扫描 {engine} 下的真实
    目录:大小写无关、requested 前缀命中目录名、最长目录名优先 —— 与
    wings_ctl.engines.version_resolver._find_prefix_version_dir 一致;另做 v 前缀
    弹性:requested "kimi-k3" 与 "vkimi-k3" 均可命中目录 "kimi-k3"。数字形态
    (0.23.0 → v0.23.0)已由句法候选覆盖,此处仅作兜底,不改变既有行为。
    """
    raw = str(engine_version).strip()
    if not raw or not engine_root.is_dir():
        return None
    requested_forms = [raw.casefold()]
    requested_forms.append(raw[1:].casefold() if raw[:1] in ("v", "V") else f"v{raw}".casefold())
    matched = [
        child.name
        for child in engine_root.iterdir()
        if child.is_dir() and any(f.startswith(child.name.casefold()) for f in requested_forms)
    ]
    return max(matched, key=lambda name: (len(name), name.casefold()), default=None)


@dataclass
class LoadFlags:
    """覆盖开关,所有字段都有默认值,不传也运行。

    MaaS 显式开关为唯一驱动:kv/sparse/decoding 是否启用 100% 由本类对应 flag 决定,
    smart_accel YAML 仅作全量占位模板(YAML 块存在不再自动启用任何特性)。KV memory
    介质另需 memory_offload_size_mode 为 auto 或数值字符串,且 YAML 需有 cpu scheme。
    """

    kv: bool = False
    sparse: bool = False
    disk: bool = False
    qat: bool = False
    disk_gb: int = 512
    disk_path: str = "/var/cache/lmcache"
    qat_devices: int = 2
    qat_level: int = 1
    decoding_enabled: bool = False
    decoding_model_path: str = ""
    sparse_level: str = "performance_first"
    pd_role: Optional[str] = None
    topology: Optional[str] = None # 部署拓扑(standalone/multi_node/pd_prefill/pd_decode);透传 DeploymentMode.topology
    # KV_MEM_OFFLOAD_SIZE: "auto" 或数值字符串(GB);空字符串/false 表示不显式下发。
    memory_offload_size_mode: str = ""
    pod_available_memory_gb: int = 0
    min_offload_threshold_gb: int = 20
    tp_size: int = 0
    dp_size: int = 0
    distributed_kv: bool = False
    distributed_protocol: str = ""
    serving_config_id: str = ""
    distributed_local_buffer_size: str = ""
    # xcache(mooncake transfer engine)安装开关;MaaS `ENABLE_XCACHE_INSTALL`,缺省 True。
    # False → DistributedKVCacheConfig.install_transfer_engine=False,跳过默认包注入。
    install_xcache: bool = True
    gpu_count: int = 0


def _has_backend_scheme(kv_offload_block) -> bool:
    """kv_offload 块里是否存在后端 scheme(声明了 daemon 脚本 ``start_kv_serve.sh`` 的 scheme)。

    判定与 ``offload._find_backend_scheme`` 同列(形态驱动,无 connector 白名单):scheme 的 ``files``
    含名为 ``start_kv_serve.sh`` 的条目 → backend(需要起卸载服务)。后端 scheme 命中即视为声明了
    内存卸载工具(cpu 介质下的实现,参与 has_memory_method)。**加新 backend connector 无需改本函数**——
    只要 yaml 的 files 里声明了 daemon 脚本就自动识别。
    """
    if not isinstance(kv_offload_block, list):
        return False
    for s in kv_offload_block:
        if not isinstance(s, dict):
            continue
        files = s.get("files") or []
        if not isinstance(files, list):
            continue
        for f in files:
            if not isinstance(f, dict):
                continue
            path = f.get("path") or f.get("name") or ""
            if Path(path).name == "start_kv_serve.sh":
                return True
    return False


def _route_smart_accel_block(smart_accel: Any, topology: Optional[str]) -> Dict[str, Any]:
    """按部署拓扑路由 smart_accel 到对应 scenario 子块(对齐 wings_control scenarios 结构)。

    新结构(对齐 wings_control,smart-yaml.md §1.1):smart_accel 按 scenario 拆块,每块带
    ``source_ref`` + ``match`` + ``strategies``;PD 分离用 ``strategies.{name}.nodes[].role`` 区分 P/D:

        smart_accel:
          standalone:
            source_ref: "..."
            match: { distributed: false, pd_role: null }
            strategies:
              single_node:
                default_strategy: true
                decoding: [...]
                sparse: [...]
                kv_offload: [...]
          multi_node:
            source_ref / match / strategies.multi_node_dp.{default + 特性}
          pd_disaggregation:
            source_ref: "..."
            match: { distributed: true, pd_role: null }
            strategies:
              pd_cluster:
                default_strategy: true
                nodes:
                  - role: prefill        # P 节点特性(如仅 sparse)
                    sparse: [...]
                  - role: decode         # D 节点特性(如 decoding + sparse)
                    decoding: [...]
                    sparse: [...]

    路由规则(对齐 wings-control Topology 枚举 + ``_select_scenario`` 语义):
      - ``topology == "multi_node"`` → ``smart_accel.multi_node.strategies.{default}``
      - ``topology == "pd_prefill"`` → ``smart_accel.pd_disaggregation.strategies.{default}.nodes[role=prefill]``
      - ``topology == "pd_decode"``  → ``smart_accel.pd_disaggregation.strategies.{default}.nodes[role=decode]``
      - 其它(含 None / "standalone" / 未知)→ ``smart_accel.standalone.strategies.{default}`` 兜底

    策略选取(对齐 wings_control ``_select_scenario``):取 ``default_strategy: true`` 的首个 strategy;
    无则取首个 strategy;strategies 为空 → 该 scenario 块整体视为缺省(空 dict)。

    PD role 匹配:``nodes[].role`` 取 ``prefill`` / ``p`` 匹配 pd_prefill,``decode`` / ``d`` 匹配 pd_decode
    (大小写不敏感);无匹配 role → 空 dict(该 role 不产出)。

    路由后的扁平 dict(含 decoding/kv_offload/sparse/custom_features 键)直接塞进
    ``SmartAccelInput.smart_accel``,expander 不再感知 scenario / topology / role。

    ``match`` 字段**仅作者自检**(wings_control 自己也不读 match,只用 topology 选键名),loader 不消费。

    Args:
        smart_accel: yaml 顶层 smart_accel dict(scenario 嵌套结构)。
        topology: 当前部署拓扑(standalone/multi_node/pd_prefill/pd_decode);None 按 standalone 兜底。

    Returns:
        路由后的扁平子块 dict(含 decoding/kv_offload/sparse/custom_features 等键);缺失 → 空 dict。
    """
    if not isinstance(smart_accel, dict) or not smart_accel:
        return {}
    topo = (topology or "standalone").strip().lower()
    if topo == "multi_node":
        return _extract_strategy_features(smart_accel.get("multi_node"))
    if topo in ("pd_prefill", "pd_decode"):
        pd = smart_accel.get("pd_disaggregation")
        strategy = _select_default_strategy(pd) if isinstance(pd, dict) else None
        if not isinstance(strategy, dict):
            return {}
        nodes = strategy.get("nodes")
        if not isinstance(nodes, list):
            return {}
        wanted = "prefill" if topo == "pd_prefill" else "decode"
        for node in nodes:
            if not isinstance(node, dict):
                continue
            role = str(node.get("role") or "").strip().lower()
            if role in (wanted, wanted[0]):  # prefill/p, decode/d
                # 返回该 node 的特性键(排除 role/index 等节点元数据)
                return {k: v for k, v in node.items() if k not in ("role", "index")}
        return {}
    # standalone / None / 未知 → standalone 兜底
    return _extract_strategy_features(smart_accel.get("standalone"))



def _routed_source_path(smart_accel: Any, topology: Optional[str]) -> str:
    """Return the original YAML path prefix for the feature block selected by routing."""
    if not isinstance(smart_accel, dict) or not smart_accel:
        return ""
    topo = (topology or "standalone").strip().lower()
    scenario_name = (
        "multi_node" if topo == "multi_node"
        else "pd_disaggregation" if topo in ("pd_prefill", "pd_decode")
        else "standalone"
    )
    scenario = smart_accel.get(scenario_name)
    if not isinstance(scenario, dict):
        return f"smart_accel.{scenario_name}"
    strategies = scenario.get("strategies")
    if not isinstance(strategies, dict) or not strategies:
        return f"smart_accel.{scenario_name}"
    strategy_name = next(
        (
            name
            for name, strategy in strategies.items()
            if isinstance(strategy, dict) and strategy.get("default_strategy") is True
        ),
        next((name for name, strategy in strategies.items() if isinstance(strategy, dict)), ""),
    )
    base = f"smart_accel.{scenario_name}.strategies.{strategy_name}"
    if topo not in ("pd_prefill", "pd_decode"):
        return base
    strategy = strategies.get(strategy_name)
    nodes = strategy.get("nodes") if isinstance(strategy, dict) else None
    wanted = "prefill" if topo == "pd_prefill" else "decode"
    if isinstance(nodes, list):
        for index, node in enumerate(nodes):
            role = str(node.get("role") or "").strip().lower() if isinstance(node, dict) else ""
            if role in (wanted, wanted[0]):
                return f"{base}.nodes[{index}]"
    return base


def _select_default_strategy(scenario: Any) -> Optional[Dict[str, Any]]:
    """从 scenario 块的 strategies 里选默认策略(对齐 wings_control ``_select_scenario``)。

    选取规则:取 ``default_strategy: true`` 的首个;无则取首个 strategy;strategies 为空 → None。

    Args:
        scenario: scenario 块 dict(含 strategies 键)。

    Returns:
        选中的 strategy dict;无 → None。
    """
    if not isinstance(scenario, dict):
        return None
    strategies = scenario.get("strategies")
    if not isinstance(strategies, dict) or not strategies:
        return None
    # 优先 default_strategy: true
    for _name, strat in strategies.items():
        if isinstance(strat, dict) and strat.get("default_strategy") is True:
            return strat
    # 无 default → 取首个
    for _name, strat in strategies.items():
        if isinstance(strat, dict):
            return strat
    return None


def _extract_strategy_features(scenario: Any) -> Dict[str, Any]:
    """从 scenario 块提取默认 strategy 的特性键(decoding/sparse/kv_offload/custom_features)。

    Args:
        scenario: scenario 块 dict(含 strategies 键)。

    Returns:
        默认 strategy 里的特性键 dict;scenario 缺 strategies → 空 dict。
    """
    strategy = _select_default_strategy(scenario)
    if not isinstance(strategy, dict):
        return {}
    # 只取特性键(排除 default_strategy 等策略元数据)
    feature_keys = ("decoding", "sparse", "kv_offload", "distributed_kv_offload", "custom_features")
    return {k: strategy[k] for k in feature_keys if k in strategy}


def load_smart_accel_from_yaml(
    yaml_path: str,
    flags: Optional[LoadFlags] = None,
) -> Optional[SmartAccelInput]:
    """读取 SmartAccel 模型 YAML,构造 SmartAccelInput。

    smart_accel 精确读取自 smart-accel model yaml 本身(不合并 default_model.yaml —— 需求1),
    嵌入 SmartAccelInput.smart_accel,func_smart_accel 直接消费,不再旁路 model_dict。
    kv_offload/decoding/sparse 等直接取自该 model yaml;缺失则对应特性不启用。

    Args:
        yaml_path: YAML 文件路径;缺失返回 None(上层按 no-op 处理)
        flags: 覆盖开关,缺省时使用 LoadFlags() 默认值

    Returns:
        SmartAccelInput: 聚合上下文 + 用户开关 + smart_accel 模板块;缺失时 None
    """
    if flags is None:
        flags = LoadFlags()

    path = Path(yaml_path)
    if not path.is_file():
        logger.warning("SmartAccel YAML not found: %s", path)
        return None

    with open(path) as f:
        model_dict = yaml.safe_load(f) or {}

    model = model_dict.get("model", {})
    hw = model_dict.get("hardware_profile", {})

    # 精确读取 smart-accel model yaml 的 smart_accel(不合并 default_model.yaml —— 需求1)
    smart_accel_raw = model_dict.get("smart_accel", {}) or {}
    # 按 topology 路由到对应 scenario 子块(scenario 嵌套结构):
    #   standalone/multi_node → 顶层对应键;pd_prefill/pd_decode → pd_disaggregation.{prefill,decode}
    #   缺键即该场景不产出;子块缺失 → 空 dict(全特性不产出)
    smart_accel = _route_smart_accel_block(smart_accel_raw, flags.topology)
    source_path = _routed_source_path(smart_accel_raw, flags.topology)

    hardware_config = SystemConfig(
        gpu_type=hw.get("gpu_type", "A100"),
        gpu_count=hw.get("gpu_count", 1),
        pod_available_memory_gb=flags.pod_available_memory_gb,
    )

    model_config = ModelConfig(
        model_path=model.get("model_id", ""),
        model_name=model.get("name"),
        model_arch=model.get("architecture"),
    )

    chosen_ec = _get_chosen_engine_config(model_dict)
    engine_config = _build_engine_config(chosen_ec)

    # kv_offload scheme:name=介质(cpu/disk/cpu_disk);后端工具(mooncake/memcache)是 cpu 介质下的实现,scheme 名也为 cpu。
    # has_memory_method = 有内存卸载方法(name 含 cpu/cpu_disk,或 yaml 声明的后端 scheme);
    # has_disk = 有 disk 层(disk 或 cpu_disk)。模板存在性护栏:memory/disk 启用还需对应方法存在。
    kv_offload_block = smart_accel.get("kv_offload")
    names = (
        {s.get("name") for s in kv_offload_block if isinstance(s, dict)}
        if isinstance(kv_offload_block, list) else set()
    )
    has_disk = "disk" in names or "cpu_disk" in names
    # 内存方法:name=cpu/cpu_disk(native/lmcache),或 yaml 声明的后端 scheme(name=cpu;mooncake/memcache 按 connector 判定)。
    # 工具按 connector 内容路由(AscendStoreConnector),不再靠 KV_STORE_BACKEND env 选。
    has_backend = _has_backend_scheme(kv_offload_block)
    has_memory_method = ("cpu" in names or "cpu_disk" in names) or has_backend

    # MaaS 显式开关为唯一驱动(YAML 块存在不再自动启用);介质另需对应 scheme 模板存在
    enable_kv = flags.kv
    enable_distributed_kv = flags.distributed_kv
    # 分布式存在性护栏(与本地 has_memory_method 护栏同构):模型 YAML 未声明
    # distributed_kv_offload(该模型未适配 Mooncake)时优雅关闭整个特性继续推理——
    # WARN 由 wings_ctl _warn_unmet_accel_switches 统一记录、页面回显 0、master Pod
    # 由 hold 段兜底;scheme 已声明但缺 kv_transfer_config 锚点仍是确定性配置错误
    # (fallback fail-fast,不走本护栏)。
    if enable_distributed_kv and smart_accel.get("distributed_kv_offload") is None:
        enable_distributed_kv = False
    enable_sparse = flags.sparse

    # 后端 scheme 选中但未下 KV_MEM_OFFLOAD_SIZE → 视为 auto(按 pod 内存估算),避免容量静默=0
    mem_size_mode_raw = flags.memory_offload_size_mode
    if has_backend and not (mem_size_mode_raw or "").strip():
        mem_size_mode_raw = "auto"
    memory_intent, memory_size_mode, memory_capacity_gb = _resolve_memory_offload(mem_size_mode_raw)

    # memory_offload_size_mode 下发 auto/数值、且 YAML 有内存方法(cpu/cpu_disk 或选中 backend)时才开
    memory_on = memory_intent is True and enable_kv and has_memory_method
    distributed_memory_on = memory_intent is True and enable_distributed_kv
    disk_on = flags.disk and enable_kv and has_disk

    # 内存卸载容量来源:auto=从 pod 内存 + TP/DP 估算 / 数值字符串=固定 GB 值
    tp = int((chosen_ec or {}).get("tensor_parallel_size") or flags.tp_size or 1)
    dp = int((chosen_ec or {}).get("data_parallel_size") or flags.dp_size or 1)
    gpu_count = flags.gpu_count
    hardware_config.gpu_count = gpu_count
    explicit_memory_on = False
    if (memory_on or distributed_memory_on) and memory_size_mode == "auto":
        est = estimate_offload_memory(
            container_memory_gb=flags.pod_available_memory_gb,
            # ``LoadFlags.gpu_count`` 是当前 Pod 中可用设备数。既有 launcher 的
            # worker 模型与它一一对应；TP×DP 仅作为未来非一一模型的显式扩展输入。
            worker_count=gpu_count,
            min_threshold_gb=flags.min_offload_threshold_gb,
        )
        if est.enabled:
            memory_capacity_gb = int(est.available_gb)
        elif explicit_memory_on:
            # 显式开启时尊重用户意图,即使估算不足也保留估算可用值(不低于 0)。
            memory_capacity_gb = max(int(est.available_gb), 0)
            logger.warning(
                "SmartAccel memory_offload_size_mode=auto estimate low but explicitly enabled: %s",
                est.disable_reason,
            )
        else:
            logger.warning("SmartAccel memory_offload_size_mode=auto: %s", est.disable_reason)
            memory_on = False
            distributed_memory_on = False
            # 分布式内存容量即特性本体(store 无容量无法启动),与本地 memory_on
            # 同分支同 WARN 地关掉整个特性——下游按 enabled=False 自然跳过,
            # 无需专门降级判定(与本地 offload 降级语义完全同构)。
            enable_distributed_kv = False

    smart_input = SmartAccelInput(
        hardware_config=hardware_config,
        model_config=model_config,
        engine_config=engine_config,
        deployment_mode=DeploymentMode(pd_role=flags.pd_role, topology=flags.topology),
        smart_decoding_config=SmartDecodingConfig(
            enabled=flags.decoding_enabled,
            model_path=flags.decoding_model_path,
        ),
        smart_kv_cache_config=SmartKVCacheConfig(
            enabled=enable_kv,
            memory_offload_enabled=memory_on,
            memory_offload_size_mode=memory_size_mode,
            disk_offload_enabled=disk_on,
            disk_capacity_gb=flags.disk_gb,
            disk_path=flags.disk_path,
            qat_enabled=flags.qat,
            qat_device_count=flags.qat_devices,
            qat_compression_level=flags.qat_level,
            tp_size=tp,
            dp_size=dp,
        ),
        distributed_kv_cache_config=DistributedKVCacheConfig(
            enabled=enable_distributed_kv,
            protocol=flags.distributed_protocol,
            serving_config_id=flags.serving_config_id,
            local_buffer_size=flags.distributed_local_buffer_size,
            memory_offload_enabled=distributed_memory_on,
            memory_offload_size_mode=memory_size_mode,
            memory_capacity_gb=memory_capacity_gb if distributed_memory_on else 0,
            disk_offload_enabled=flags.disk and enable_distributed_kv,
            disk_capacity_gb=flags.disk_gb,
            disk_path=flags.disk_path,
            install_transfer_engine=flags.install_xcache,
        ),
        smart_kv_sparse_config=SmartKVSparseConfig(enabled=enable_sparse, mode=flags.sparse_level),
        smart_accel=smart_accel,
        source_file=str(path),
        source_path=source_path,
    )
    # 内部渲染容量:不作为 SmartKVCacheConfig 入参暴露,由 loader 根据 memory_offload_size_mode 解析。
    setattr(smart_input.smart_kv_cache_config, "_memory_capacity_gb", memory_capacity_gb)

    return smart_input


def _resolve_memory_offload(value: Optional[str]) -> tuple[Optional[bool], str, int]:
    """解析 KV_MEM_OFFLOAD_SIZE/ENABLE_KV_MEM_OFFLOAD:auto / 数值 GB / false / 未下发。"""
    if value is None:
        return None, "", 0
    raw = str(value).strip().lower()
    if raw in ("", "false", "0", "no", "off"):
        return False, "", 0
    if raw == "auto":
        return True, "auto", 0
    try:
        return True, raw, int(raw)
    except ValueError:
        logger.warning("Invalid memory_offload_size_mode=%r, disable memory offload", value)
        return False, "", 0


def _package_smart_accel_root() -> Path:
    """返回随 wings_accel 包分发的 smart-accel YAML 根目录。"""
    return Path(__file__).resolve().parent / "smart-accel"


def is_package_smart_accel_source(source_file: Union[str, Path]) -> Optional[bool]:
    """判断实际命中的 SmartAccel YAML 是否位于随包分发的资产根内。

    Args:
        source_file: 已加载的 SmartAccel YAML 路径。

    Returns:
        True 表示包内资产;False 表示外部资产;无法确认时返回 None。
    """
    if not source_file:
        return None
    try:
        resolved_source = Path(source_file).resolve()
        package_root = _package_smart_accel_root().resolve()
    except (OSError, RuntimeError):
        return None
    if not resolved_source.is_file():
        return None
    return resolved_source.is_relative_to(package_root)


def _resolve_smart_accel_root(config_root: Union[str, Path]) -> Path:
    """优先使用 config_root/smart-accel,否则回落到包内 smart-accel。"""
    root = Path(config_root) / "smart-accel"
    if root.exists():
        return root
    return _package_smart_accel_root()


def build_smart_accel_yaml_path(
    config_root: Union[str, Path],
    engine: str,
    engine_version: str,
    hardware_family: str,
    model_dir: str,
    yaml_name: str,
) -> Path:
    """拼 SmartAccel 配置路径。

    目录固定为 wings_accel/smart-accel/{engine}/v{version}/{hardware}/models/{model_dir}/{yaml_name}。
    config_root 参数保留用于兼容旧调用;若调用方显式传入带 smart-accel 的根目录,优先用于测试/外部覆盖。
    新调用优先使用 find_smart_accel_yaml_path 按 hardware models 目录扫描匹配。
    """
    root = _resolve_smart_accel_root(config_root)
    # 与 find 相同的解析顺序:句法候选(精确→基础→渠道归一)→ 自定义版本目录前缀扫描;
    # 全部落空时保留旧行为(最后一个句法候选/补 v),供纯拼路径场景使用。
    candidates = _candidate_version_dirs(str(engine_version))
    for version_dir in candidates:
        if (root / engine / version_dir / hardware_family).is_dir():
            return root / engine / version_dir / hardware_family / "models" / model_dir / yaml_name
    scanned = _scan_prefix_version_dir(root / engine, str(engine_version))
    if scanned and (root / engine / scanned / hardware_family).is_dir():
        version_dir = scanned
    else:
        version_dir = candidates[-1] if candidates else f"v{str(engine_version).lstrip('v')}"
    return root / engine / version_dir / hardware_family / "models" / model_dir / yaml_name


def find_smart_accel_yaml_path(
    config_root: Union[str, Path],
    engine: str,
    engine_version: str,
    hardware_family: str,
    model_name: str,
) -> Optional[Path]:
    """按硬件目录扫描并匹配 SmartAccel YAML —— 三层优先级(对齐 docs/48 + 保留 stem 兜底)。

    MaaS 不下发精度参数,变体信号 = ``--model-name`` 带完整精度后缀(如 ``Qwen3.5-397B-A17B-nvfp4``)。
    匹配优先级(逐层回退,每层 1 命中→取 / >1 命中→报错 / 0 命中→落下一层):
    1. ``model.variant_name`` 与 model_name 小写归一**精确相等**(非正则)—— 确定性,无子串坑(docs/48 主路径)。
    2. ``model.match[].name_pattern`` 正则命中 model_name —— 家族级模糊兜底(docs/48 回退层)。
    3. ``model.name`` / ``model.model_id`` / 模型目录名 / yaml stem 与 model_name 精确匹配
       —— 单变体向后兼容兜底(存量无 model 块的 yaml 仍可定位)。

    全部 0 命中返回 None(上层 no-op)。

    Args:
        config_root: 配置根目录;优先 config_root/smart-accel,否则回落包内 smart-accel。
        engine: 引擎名(vllm / vllm-ascend / sglang)。
        engine_version: 引擎版本,可带可不带 v 前缀。
        hardware_family: 硬件目录名,如 rtx_pro_5000_48G。
        model_name: 待匹配模型名(= MaaS 下发的 --model-name,带完整精度后缀)。

    Returns:
        匹配的 yaml Path;无命中返回 None。

    Raises:
        ValueError: 某层命中 >1(variant_name 冲突 / name_pattern 或 stem 多变体歧义),
            错误信息带 model_name + 候选清单,避免静默选错。
    """
    root = _resolve_smart_accel_root(config_root)
    # 按"原始版本目录 → 归一化渠道目录"顺序查找,兼容构建版本号
    # (如 v0.21.0rc1-20260709144216 → v0.21.0rc)。与 version_resolver 候选顺序对齐:精确优先。
    candidate_dirs = _candidate_version_dirs(str(engine_version))
    models_dir: Optional[Path] = None
    for version_dir in candidate_dirs:
        candidate = root / engine / version_dir / hardware_family / "models"
        if candidate.is_dir():
            models_dir = candidate
            break
    if models_dir is None:
        # 自定义版本目录(非数字形态,如 kimi-k3 / kimi-k3-a3)无法靠句法候选展开,
        # 按引擎侧 version_resolver 的前缀语义扫描真实目录(大小写无关、requested
        # 前缀命中目录名、最长优先,v 带/不带均可),requested 形如
        # "kimi-k3-a3-20260730213841" 也可命中目录 "kimi-k3-a3"。
        scanned = _scan_prefix_version_dir(root / engine, str(engine_version))
        if scanned:
            candidate = root / engine / scanned / hardware_family / "models"
            if candidate.is_dir():
                logger.info(
                    "SmartAccel: engine_version '%s' prefix-matched version dir '%s'",
                    engine_version, scanned,
                )
                models_dir = candidate
    if models_dir is None:
        logger.warning(
            "SmartAccel models dir not found under %s/%s/[candidates=%s]/%s",
            root, engine, candidate_dirs, hardware_family,
        )
        return None

    # 三层分桶:同一文件只入其命中的最高优先层(if/elif),逐层判定,与 docs/48 逐层回退等价。
    exact_variant: list[Path] = []   # ① variant_name 精确
    pattern_hits: list[Path] = []    # ② name_pattern 正则
    stem_hits: list[Path] = []       # ③ 目录名/stem 精确兜底
    yaml_errors: list[tuple[Path, str]] = []
    for yaml_file in sorted(models_dir.glob("*/*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            yaml_errors.append((yaml_file, str(exc)))
            logger.warning("SmartAccel YAML parse failed %s: %s", yaml_file, exc)
            continue
        if not isinstance(data, dict):
            continue
        if _match_variant_name(data, model_name):
            exact_variant.append(yaml_file)
        elif _match_name_pattern(data, yaml_file, model_name):
            pattern_hits.append(yaml_file)
        elif _match_stem(data, yaml_file, model_name):
            stem_hits.append(yaml_file)

    # ① variant_name 精确优先(确定性,docs/48 主路径)
    if len(exact_variant) == 1:
        logger.info("SmartAccel: model '%s' exactly matched variant_name in %s", model_name, exact_variant[0])
        return exact_variant[0]
    if len(exact_variant) > 1:
        raise ValueError(
            f"variant_name 冲突:多个 SmartAccel YAML 声明 variant_name='{model_name}': "
            + ", ".join(str(p) for p in exact_variant)
            + "。请确保同目录 variant_name 两两不重复。"
        )

    # ② name_pattern 模糊回退
    if len(pattern_hits) == 1:
        logger.info("SmartAccel: model '%s' name_pattern matched in %s", model_name, pattern_hits[0])
        return pattern_hits[0]
    if len(pattern_hits) > 1:
        raise ValueError(
            f"Ambiguous SmartAccel YAML: model_name='{model_name}' 经 name_pattern 命中多个文件: "
            + ", ".join(str(p) for p in pattern_hits)
            + "。多变体请传带精度后缀的完整 --model-name(= 各文件 model.variant_name)。"
        )

    # ③ 目录名/stem 精确兜底(单变体向后兼容)
    if len(stem_hits) == 1:
        logger.info("SmartAccel: model '%s' stem/dir matched in %s", model_name, stem_hits[0])
        return stem_hits[0]
    if len(stem_hits) > 1:
        raise ValueError(
            f"Ambiguous SmartAccel YAML: model_name='{model_name}' 命中多个文件(目录名/stem): "
            + ", ".join(str(p) for p in stem_hits)
        )

    msg = f"No SmartAccel YAML matched model_name='{model_name}' under {models_dir}"
    if yaml_errors:
        details = "; ".join(f"{p}: {e}" for p, e in yaml_errors)
        msg += f"; YAML parse errors encountered: {details}"
    logger.warning(msg)
    return None


def load_smart_accel_from_config(
    config_root: Union[str, Path],
    engine: str,
    engine_version: str,
    hardware_family: str,
    model_name: str,
    flags: Optional[LoadFlags] = None,
) -> Optional[SmartAccelInput]:
    """按 smart-accel 硬件目录扫描定位并读取模型 YAML;缺失返回 None。"""
    yaml_path = find_smart_accel_yaml_path(
        config_root,
        engine,
        engine_version,
        hardware_family,
        model_name,
    )
    if yaml_path is None:
        return None
    smart_input = load_smart_accel_from_yaml(str(yaml_path), flags)
    if smart_input is not None:
        # 调用方选择的 engine/version 是 SmartAccel 资产定位与 runtime 选择的权威上下文。
        # 不能让模型 YAML 缺失 scenarios.engine_config 时回退 EngineConfig() 的 vllm 默认值，
        # 否则 vllm-ascend 会错误选择 mooncake_cuda。
        smart_input.engine_config = EngineConfig(name=engine, version=engine_version)
        # smart-accel 根目录供 files 条目 src 解析。
        smart_input.config_root = str(_resolve_smart_accel_root(config_root))
    return smart_input


def _match_variant_name(data: Dict[str, Any], model_name: str) -> bool:
    """① 精确层:model.variant_name 与 model_name 小写归一后精确相等(非正则)。

    variant_name = MaaS 对本文件下发的【完整 --model-name】(带精度后缀);显式声明、不推断。
    docs/48 主路径:精确相等无正则子串坑,多变体发全名即唯一命中。

    Args:
        data: 已解析的 yaml dict。
        model_name: 待匹配模型名。

    Returns:
        variant_name 存在且与 model_name 精确相等(忽略大小写/首尾空白)→ True;否则 False。
    """
    model_block = data.get("model", {})
    if not isinstance(model_block, dict):
        return False
    variant_name = model_block.get("variant_name")
    if not isinstance(variant_name, str) or not variant_name.strip():
        return False
    return variant_name.strip().lower() == model_name.strip().lower()


def _match_name_pattern(data: Dict[str, Any], yaml_file: Path, model_name: str) -> bool:
    """② 模糊层:model.match[].name_pattern 正则 re.search 命中 model_name(家族级兜底)。

    docs/48 回退层:精确层零命中时,用家族级 name_pattern 容错(家族名/大小写漂移/向后兼容)。
    非法正则不中断全量扫描:记日志后跳过该规则。

    Args:
        data: 已解析的 yaml dict。
        yaml_file: yaml 路径(仅用于非法正则的日志定位)。
        model_name: 待匹配模型名。

    Returns:
        任一 name_pattern 命中 → True;否则 False。
    """
    model_block = data.get("model", {})
    if not isinstance(model_block, dict):
        return False
    match_rules = model_block.get("match", [])
    if not isinstance(match_rules, list):
        return False
    for rule in match_rules:
        if not isinstance(rule, dict):
            continue
        pattern = rule.get("name_pattern", "")
        if not pattern:
            continue
        try:
            if re.search(pattern, model_name):
                return True
        except re.error as exc:
            logger.warning(
                "SmartAccel: invalid name_pattern %r in %s: %s (skip this rule)",
                pattern, yaml_file, exc,
            )
            continue
    return False


def _match_stem(data: Dict[str, Any], yaml_file: Path, model_name: str) -> bool:
    """③ 向后兼容兜底:model.name / model.model_id / 目录名 / yaml stem 与 model_name 精确相等。

    供无 model 块的存量单变体 yaml 定位。docs/48 不推荐用 model_id/文件名做消歧键
    (真实数据证明不可靠),但 wings_accel 存量 yaml 依赖此兜底,作最低优先层保留。

    Args:
        data: 已解析的 yaml dict。
        yaml_file: yaml 路径(取 parent.name / stem 作候选)。
        model_name: 待匹配模型名。

    Returns:
        任一候选与 model_name(或其 basename)小写归一后相等 → True;否则 False。
    """
    model_block = data.get("model", {}) if isinstance(data.get("model"), dict) else {}
    candidates = [model_block.get("name"), model_block.get("model_id")]
    candidates.extend([yaml_file.parent.name, yaml_file.stem])
    names = {_normalize_model_name(v) for v in candidates if v}
    requested = {
        _normalize_model_name(model_name),
        _normalize_model_name(Path(model_name).name),
    }
    return bool(names & requested)


def _normalize_model_name(value: str) -> str:
    """模型名匹配用的轻量归一化。"""
    return str(value).strip().lower()


def _get_chosen_engine_config(model_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 scenarios.{topology}.strategies.{name}.engine_config 取选中的 engine_config dict。

    取第一个 default_strategy=true 的策略;若都没有,取第一个策略。
    缺失时返回 None。
    """
    scenarios = model_dict.get("scenarios", {}) or {}
    for _, topo_block in scenarios.items():
        strategies = (topo_block or {}).get("strategies", {}) or {}
        default_block = None
        first_block = None
        for _, strat in strategies.items():
            if first_block is None:
                first_block = strat
            if (strat or {}).get("default_strategy"):
                default_block = strat
                break
        chosen = default_block or first_block
        if chosen and chosen.get("engine_config"):
            return chosen["engine_config"]
    return None


def _build_engine_config(ec: Optional[Dict[str, Any]]) -> EngineConfig:
    """从 engine_config dict 构建 EngineConfig。

    缺失时返回 EngineConfig() 默认值(vllm / 0.22.0)。
    """
    if not ec:
        return EngineConfig()
    return EngineConfig(
        name=ec.get("engine", "vllm"),
        version=ec.get("version", "0.22.0"),
    )
