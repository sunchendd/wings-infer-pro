"""
数据契约层 — SmartAccel 全部输入输出数据结构。

定义模块的输入输出边界:
- SmartAccelInput: 总输入,聚合系统/模型/引擎/部署模式 + 三个 smart 配置 + smart_accel 模板块
- SmartAccelOutput: 总输出,选中 scheme + 合并后的 EngineParams + 降级诊断
- EngineParams: 单个特性的产出形态(结构化引擎参数 + 环境变量)
- _FeatureOutput: expander 内部返回形态(scheme 名 + EngineParams + 降级标记),不对外导出

重要关键点:
- 该文件只定义数据契约,不包含选择/渲染逻辑。
- SmartAccelInput 是 func_smart_accel 唯一输入;SmartAccelOutput 是对 wings-control 的增量输出。
- EngineParams 承载已填充占位符的 env + engine_config,不是预渲染 argv。
- diagnostics 只承载 wings-control 推不出的降级信息;未降级特性不出现。
- _FeatureOutput 仅供包内 expander/conflict/core 传递 scheme 与降级信息。

设计要点:
- 所有可空字段使用 Optional,避免构造时传 None 报错
- 可变默认值使用 field(default_factory=...) 防止跨实例污染
- 与 wings_ctl 的 trace 体系解耦,诊断信息以扁平 dict 承载
- 渲染落点:各 expander 用 render.render_engine_config 把 YAML cli_params 转成
  engine_config 字典,由 wings-control 负责最终 argv 渲染。

字段注释里的「MaaS 来源」标注每个字段对应的产品侧(MaaS)入参:
  - `--xxx`  = 用户 CLI 参数(auto 选填类 CLI 不下发即 False)
  - `XXX`    = 环境变量/特性开关(未下发的 bool 开关由 wings-control 按 False 处理)
  - 「非 MaaS 参数」= 来自 model.yaml / 路径定位,不由 MaaS 用户填写
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class SmartAccelConfigurationError(ValueError):
    """SmartAccel 资产或安全边界不满足时的确定性配置错误,调用方必须 fail-fast。"""


@dataclass
class SystemConfig:
    """系统配置 — 承载硬件族(定位 smart-accel yaml)+ 卡数 + pod 可用内存。

    yaml 定位键之一:engine + version + hardware_family + model_name。
    目录: wings_accel/smart-accel/{engine}/v{version}/{hardware_family}/models/{model}/*.yaml

    MaaS 对齐:
      - `--device-count`:必填,int,卡数。
      - `AVAILABLE_POD_MEM_SIZE`:必填,int,pod 可用内存大小,单位 **MiB**(如 65536 表示 64GB);当前消费方为 KV 卸载,
        后续也可被其他特性消费。注:入口换算为 GB 后再扣 15GB(MaaS 页面下发口径补偿,页面 bug 实际下发=总内存−5GB,
        正确契约=总内存−20GB;页面修复后移除)。
    """

    gpu_type: str = "A100" # 硬件族(= hardware_family,如 rtx_pro_5000_72G / h200);yaml 定位键,非 MaaS 直接入参
    gpu_count: int = 1 # 卡数;MaaS 必填 `--device-count`(int;不参与 yaml 定位)
    pod_available_memory_gb: int = 0 # pod 可用内存(GB);MaaS 必填 `AVAILABLE_POD_MEM_SIZE`(int MiB,入口 /1024 换算)


@dataclass
class ModelConfig:
    """主模型元数据 — 模型名称(定位 yaml)+ 架构族(decoder 选草稿)+ 权重路径。

    model_name 是 yaml 定位键之一(与 engine / hardware_family 组合)。
    注意与 SmartDecodingConfig.model_path 区分:这里是【主模型】路径,
    SmartDecodingConfig.model_path 是投机解码的【草稿模型】路径。
    """

    model_path: str # 主模型权重路径(HF repo id / 本地);MaaS 来源 `--model-path`
    model_name: Optional[str] = None # 模型名称;yaml 定位键之一;MaaS 来源 `--model`/`-m`(name_pattern 匹配)
    model_arch: Optional[str] = None # 模型架构族(llama / glm / eagle3 ...);来源 model.yaml `architecture`(decoders 据此选草稿方法)


@dataclass
class EngineParams:
    """单个特性的产出形态 — 结构化引擎参数 + 环境变量。

    decoding / kv_cache / sparse / custom_features 各产出一个,是 func_smart_accel
    与 wings-control 之间的增量交付单元:engine_config 由 wings-control 渲染为 argv,
    env 注入容器。本类为【产出】,无 MaaS 来源。
    """

    env: Dict[str, str] = field(default_factory=dict) # 要注入容器的环境变量(K=V);产出侧
    engine_config: Dict[str, Any] = field(default_factory=dict) # 结构化引擎参数(如 {"speculative_config": {...}});产出


class SmartAccelPackageFormatError(SmartAccelConfigurationError):
    """SmartAccel ``packages`` 声明不是精确的 ``name:version`` 依赖。"""


class SmartAccelPackageConflictError(SmartAccelConfigurationError):
    """多个 SmartAccel feature 为同一规范化包名声明了不同版本。"""


@dataclass(frozen=True)
class PackageRequirement:
    """已解析的精确 Python 包依赖。

    交付(install 段 ``--config``)保留 YAML 首次声明的原始 ``name:version``:
    wings-accel ``install.py`` 对 manifest 的包名/版本键做**精确查找**,镜像包
    目录名保留 ``v`` 前缀(如 ``packages/lmcache-ascend/v0.4.5``),改写为
    canonical 名/去 ``v`` 版本会 ``Package not found``。规范化值只用于跨 feature
    冲突比较(同 canonical 名 + 不同版本比较键 → 冲突)。
    """

    name: str # YAML 声明的原始包名(交付用)
    version: str # YAML 声明的原始版本串(如 v0.4.5;交付用)
    canonical_name: str # canonicalize_name 规范化包名(冲突比较键)
    canonical_version: str # PEP 440 规范化版本或其他交付版本原文(冲突比较键)

    @property
    def manifest(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass
class GeneratedFile:
    """解析期生成的文件计划,由 wings-control 在产物阶段负责写盘。"""

    path: str
    content: str
    mode: Optional[str] = None
    scope: str = "all"
    source_file: str = ""
    source_path: str = ""
    runtime_vars: List[str] = field(default_factory=list)


@dataclass
class EngineConfig:
    """引擎标识 — 名称 + 版本,用于版本解析与能力分流。"""

    name: str = "vllm" # 引擎类型;MaaS 必填 `--engine`(str,使用连接符,如 vllm-ascend)
    version: str = "0.22.0" # 引擎版本字符串;MaaS 必填 `ENGINE_VERSION`(str)


@dataclass
class SmartDecodingConfig:
    """智能投机解码配置 — speculative decoding 的开关与草稿来源。

    MaaS 对齐:
      - `ENABLE_SPECULATIVE_DECODE`:必填,bool,投机推理开关(smart 一级),取值 true/false;
        AI perf 未传时 wings-control 按 False 处理。
      - `SPECULATIVE_DECODE_MODEL_PATH`:条件必填,str;当 ENABLE_SPECULATIVE_DECODE=true 时必填
        (本地挂载的草稿模型目录或 none;仅消费目录,config.json 文件路径/HF repo id 不接受),false 时不下发。
    """

    enabled: bool = False # 投机推理开关;MaaS 必填 `ENABLE_SPECULATIVE_DECODE`(bool true/false;缺省按 False)
    model_path: str = "" # 草稿模型路径(本地挂载的模型目录或 none);MaaS 条件必填 `SPECULATIVE_DECODE_MODEL_PATH`(spec=true 时目录或 none)


@dataclass
class SmartKVCacheConfig:
    """智能 KV cache 卸载配置 — CPU/磁盘两级卸载容量 + QAT 硬件压缩。

    offload.py 据此选择介质、由 render.py 填占位符;capacity 类字段在
    memory_offload_size_mode="auto" 时由 memory_estimator 估算后回填。

    memory_offload_size_mode:
      - "" / false:不显式下发 CPU 内存卸载
      - "auto"    :从 SystemConfig.pod_available_memory_gb + TP/DP 估算可用 CPU 内存,不足阈值则关闭 memory_offload
      - 数值字符串:按 GB 固定配置

    MaaS 对齐:
      - `ENABLE_KV_OFFLOAD`:必填,bool,KV 卸载开关(smart 一级),取值 true/false;AI perf 未传时
        wings-control 按 False 处理。它控制二级开关 `ENABLE_KV_MEM_OFFLOAD` 和 `ENABLE_KV_DISK_OFFLOAD`。
      - `ENABLE_KV_MEM_OFFLOAD`:条件必填,bool;ENABLE_KV_OFFLOAD=true 时必填,false 时不下发。
      - `KV_MEM_OFFLOAD_SIZE`:条件必填,str;ENABLE_KV_MEM_OFFLOAD=true 时必填,false 时不下发;
        取值为字符串 "auto" 或数值字符串 "xx"(单位 GB),"auto" 表示智能推荐。
      - `ENABLE_KV_DISK_OFFLOAD`:条件必填,bool;ENABLE_KV_OFFLOAD=true 时必填,false 时不下发;
        同时控制三级开关 `ENABLE_KV_QAT`。
      - `KV_DISK_OFFLOAD_PATH`:条件必填,str;ENABLE_KV_DISK_OFFLOAD=true 时必填,false 时不下发。
      - `KV_DISK_OFFLOAD_SIZE`:条件必填,int;ENABLE_KV_DISK_OFFLOAD=true 时必填,false 时不下发;
        数值单位 GB。
      - `ENABLE_KV_QAT`:条件必填,bool;ENABLE_KV_DISK_OFFLOAD=true 时必填,false 时不下发。
      - `KV_QAT_COMPRESS_LEVEL`:条件必填,int;ENABLE_KV_QAT=true 时必填,false 时不下发。
      - `KV_QAT_INSTANCE_NUM`:条件必填,int;ENABLE_KV_QAT=true 时必填,false 时不下发。
    """

    enabled: bool = False # KV 卸载一级开关;MaaS 必填 `ENABLE_KV_OFFLOAD`(bool true/false;缺省按 False)
    memory_offload_enabled: bool = False # KV 内存卸载二级开关;MaaS 条件必填 `ENABLE_KV_MEM_OFFLOAD`(kv=true 时必填)
    memory_offload_size_mode: str = "" # KV 卸载内存大小;MaaS 条件必填 `KV_MEM_OFFLOAD_SIZE`("auto" 或数值字符串,GB)
    disk_offload_enabled: bool = False # 磁盘卸载二级开关;MaaS 条件必填 `ENABLE_KV_DISK_OFFLOAD`(kv=true 时必填)
    disk_capacity_gb: int = 0 # KV 卸载磁盘大小;MaaS 条件必填 `KV_DISK_OFFLOAD_SIZE`(int,GB)
    disk_path: str = "" # 磁盘路径;MaaS 条件必填 `KV_DISK_OFFLOAD_PATH`(disk=true 时必填)
    qat_enabled: bool = False # QAT 三级开关;MaaS 条件必填 `ENABLE_KV_QAT`(disk=true 时必填)
    qat_device_count: int = 0 # QAT 设备数量;MaaS 条件必填 `KV_QAT_INSTANCE_NUM`(qat=true 时必填)
    qat_compression_level: int = 0 # QAT 压缩等级;MaaS 条件必填 `KV_QAT_COMPRESS_LEVEL`(qat=true 时必填)
    # ── KV 存储后端(AscendStoreConnector:memcache / mooncake)—— cpu 介质下的内存卸载工具(name=cpu,非第四类介质)──
    # 选中后产 kv_transfer_config(backend) + 配置文件 + pre-serve daemon(mooncake_master / MetaService);
    # 作为 cpu 内存方法参与 (memory_on, disk_on) 选择(工具由 connector + kv_connector_extra_config.backend 区分)。

    tp_size: int = 0 # TP SIZE大小。通过recipe解析微调后传递
    dp_size: int = 0 # DP SIZE大小。通过recipe解析微调后传递(对齐 tp_size;供下游 PlaceholderContext/模板渲染用)


@dataclass
class DistributedKVCacheConfig:
    """Mooncake standalone-store 分布式 KV 缓存的外部输入。

    该配置与 ``SmartKVCacheConfig`` 并列：前者只控制本地 KV 卸载，后者只控制
    每 Pod 一个 Mooncake real client。两者不能同时启用，因为 vLLM 只接受一个
    ``kv_transfer_config``。

    ``enabled=False`` 的三种来源(下游均按未启用自然跳过,与本地降级同构):
    MaaS 开关未开 / auto 估算不足(loader 同一分支关闭)/ 模型 YAML 未声明
    ``distributed_kv_offload``(loader 存在性护栏,优雅关闭继续推理)。

    memory_offload_size_mode(与 ``SmartKVCacheConfig`` 同名口径):
      - "" / false:不显式下发内存容量
      - "auto"    :智能推荐——复用 memory_estimator 按 pod 内存 + 卡数估算 store
                    可用内存;估算不足阈值时 loader 在与本地同一分支同时置
                    enabled/memory_offload 为 False(单 WARN、不阻断),下游按
                    未启用自然跳过(降级语义与本地卸载完全同构)
      - 数值字符串:按 GB 固定配置
    """

    enabled: bool = False
    protocol: str = ""
    serving_config_id: str = ""
    local_buffer_size: str = ""
    memory_offload_enabled: bool = False
    memory_offload_size_mode: str = "" # KV 卸载内存大小模式;MaaS `KV_MEM_OFFLOAD_SIZE`("auto" 或数值字符串,GB)
    memory_capacity_gb: int = 0
    disk_offload_enabled: bool = False
    disk_capacity_gb: int = 0
    disk_path: str = ""
    # xcache(mooncake transfer engine)安装开关;MaaS `ENABLE_XCACHE_INSTALL`(缺省 True)。
    # False = 跳过默认包注入、不解析 accel-version(假定引擎镜像已预装 xcache);
    # 仅影响 install 段,YAML scheme 显式声明的同名包不受此开关影响(声明优先)。
    install_transfer_engine: bool = True


@dataclass
class SmartKVSparseConfig:
    """KV cache 稀疏化配置 — 按策略裁剪/跳过 KV 以省显存。

    MaaS 对齐:
      - `ENABLE_SPARSE`:必填,bool,KV 稀疏开关(smart 一级),取值 true/false;
        AI perf 未传时 wings-control 按 False 处理。
      - `SPARSE_LEVEL`:条件必填,enum;ENABLE_SPARSE=true 时必填,false 时不下发;
        枚举值 accuracy_first / performance_first。
    """

    enabled: bool = False # KV 稀疏开关;MaaS 必填 `ENABLE_SPARSE`(bool true/false;缺省按 False)
    mode: str = "performance_first" # 稀疏模式;MaaS 条件必填 `SPARSE_LEVEL`(accuracy_first/performance_first)


@dataclass
class DeploymentMode:
    """部署模式 — PD 分离(prefill/decode 解耦部署)角色。

    MaaS 对齐:
      - `--distributed`:auto 选填,bool;下发表示 true,不下发表示 false。
      - `MASTER_IP` / `RANK_IP` / `NODE_IPS`:条件必填,str;--distributed 下发时必填,
        不下发时不下发。上述分布式字段由 wings-control 拓扑层消费,不进入本 dataclass。
      - `PD_ROLE`:必填,enum,取值 P / D / none。
      - `--enable-rag-acc` / `--enable-smartqos` / `--enable-otlp-traces`:auto 选填,bool;
        下发表示 true,不下发表示 false。`OTLP_TRACES_ENDPOINT` 在 --enable-otlp-traces 下发时条件必填。
    """

    pd_role: Optional[str] = None # PD 角色;MaaS 必填 `PD_ROLE`(enum:P/D/none;none 表示非 PD 分离)
    # 部署拓扑(standalone/multi_node/pd_prefill/pd_decode);对齐 wings-control Topology 枚举值。
    # yaml_loader 据此把 smart_accel 路由到对应 scenario 子块(见 smart-yaml.md §1)。
    topology: Optional[str] = None


def scheme_supports_deploy_mode(scheme: Dict[str, Any], topology: Optional[str]) -> bool:
    """判断 scheme 是否声明支持当前部署拓扑。

    .. deprecated:: scenario 重构(2026-08-06)
        scenario 嵌套结构后,smart_accel 按 topology 路由在 ``yaml_loader._route_smart_accel_block``
        完成,expander 拿到的就是当前 scenario 的扁平子块,**不再需要 scheme 级 deploy_modes 过滤**。
        本函数仅作向后兼容保留(避免破坏外部 import / 旧调用),新代码不应再调用;新结构 yaml 也不应
        再声明 ``deploy_modes`` 字段。

    旧语义(scheme 级 deploy_modes 白名单):

      - scheme 的 ``deploy_modes`` 字段(可选 list)声明该 scheme 产出的部署模式白名单:
        未声明(缺字段/None/空)→ 支持所有模式;声明了 → 仅当 ``topology`` 在白名单内才支持。
      - ``deploy_modes`` 取值对齐 wings-control ``Topology`` 枚举:
        ``standalone`` / ``multi_node`` / ``pd_prefill`` / ``pd_decode``。

    Args:
        scheme: decoding/kv_offload/sparse 的单个方案 dict。
        topology: 当前部署拓扑(``DeploymentMode.topology``);None 时按 standalone 兜底。

    Returns:
        True 表示 scheme 可在当前拓扑产出。
    """
    modes = scheme.get("deploy_modes")
    if not modes:  # None / [] / 缺字段 → 全场景
        return True
    if not isinstance(modes, list):
        return True  # 非法写法兜底放行(避免误拦全部资产);由 yaml schema 校验把关
    current = topology or "standalone"
    return current in modes


@dataclass
class SmartAccelInput:
    """总输入 — 聚合系统/模型/引擎/部署模式 + 三个 smart 子配置 + smart_accel 模板块。

    由 yaml_loader.load_smart_accel_from_yaml 从 model.yaml 构造,func_smart_accel 消费。
    smart_accel 模板块(decoding methods / kv_offload schemes / sparse schemes / custom_features)
    精确读取自 model.yaml,由各 expander 展开。各字段来源见对应子配置类。
    """

    hardware_config: SystemConfig # 系统配置(硬件族定位 yaml + pod 内存)
    model_config: ModelConfig # 主模型元数据(model_name 定位 yaml / model_arch 选草稿)
    engine_config: EngineConfig # 引擎标识(定位 yaml;sglang → 全 None)
    deployment_mode: DeploymentMode # 部署模式(PD 角色)
    smart_decoding_config: SmartDecodingConfig # 投机解码配置(开关 + 草稿路径)
    smart_kv_cache_config: SmartKVCacheConfig # KV 卸载 + QAT 配置(开关 + 容量模式)
    smart_kv_sparse_config: SmartKVSparseConfig # KV 稀疏化配置(开关 + 模式)
    distributed_kv_cache_config: DistributedKVCacheConfig = field(default_factory=DistributedKVCacheConfig)
    # smart_accel 模板块(decoding/kv_offload/sparse/custom_features),来自 model.yaml
    smart_accel: Dict[str, Any] = field(default_factory=dict)
    # smart-accel 根目录(_resolve_smart_accel_root 结果);files 条目 src 解析基准。非 MaaS 参数,
    # 由 yaml_loader.load_smart_accel_from_config 在构造时填入。
    config_root: str = ""
    # Actual selected SmartAccel YAML and routed source path for generated-file audit.
    source_file: str = ""
    source_path: str = ""


@dataclass
class _FeatureOutput:
    """expander 内部返回形态 — 选中的 scheme 名 + 已渲染 EngineParams + 降级标记。

    不对外导出。scheme 名供 core 写入 SmartAccelOutput 选中字段;
    engine_params 最终合并到 SmartAccelOutput.engine_params;packages 汇总到
    SmartAccelOutput.packages(供 install 段拼 ``--config`` 的依赖列表)。
    """

    scheme: str # 选中的 scheme 名(如 "eagle3" / "cpu" / "performance_first")
    engine_params: EngineParams # 已填充占位符的 env + engine_config
    degraded: bool = False # 是否发生降级
    degrade_reason: str = "" # 降级原因
    packages: List[PackageRequirement] = field(default_factory=list) # 选中 scheme 声明的规范化精确 pip 依赖
    pre_serve: List[str] = field(default_factory=list) # 所有节点在引擎启动前执行的框架合成命令
    pre_serve_master: List[str] = field(default_factory=list) # 仅 master 节点执行的框架合成命令
    pre_serve_client: List[str] = field(default_factory=list) # 仅 client(非 master)节点执行的框架合成命令
    generated_files: List[GeneratedFile] = field(default_factory=list) # 已渲染、未写盘的文件计划;由 wings-control 在产物阶段消费
    # True 时 script_builder 将随包的脚本兜底资产复制到共享卷。
    mooncake_script_assets_required: bool = False
    # Mooncake master 分支段(early-exit 块的 shell 行)。仅 distributed_offload
    # 使用;由受控包代码合成,非 YAML 任意 shell。空 → script_builder 不渲染该段。
    mooncake_master_section: List[str] = field(default_factory=list)
    # 传输引擎包("name:version",保留声明/目录名原样)。mooncake_master 二进制随该包
    # 交付(install.py 以包内版本覆盖镜像预装旧版),master Pod 不跑引擎但拉起 master
    # 须装它;script_builder 的 master 交付支线据此单独渲染只含该包的 install 段。
    # None = 未声明且未注入(ENABLE_XCACHE_INSTALL=false / 特性未启用),镜像预装兜底。
    mooncake_transfer_engine_package: Optional[str] = None


@dataclass
class SmartAccelOutput:
    """总输出 — 选中方案名 + 合并后的 EngineParams + 降级诊断。

    func_smart_accel 产出,wings-control 据此把 engine_params.env 注入容器,
    把 engine_params.engine_config 渲染为 argv。scheme 字段只表达各 smart 特性最终选中了什么;未产出则为 None。

    diagnostics 只放 wings-control 推不出的降级信息,形如
    {"decoding": {"degraded": True, "degrade_reason": "..."}};未降级特性不出现。

    特殊:engine 为 sglang 时 scheme 全部为 None,engine_params 为空。
    custom_features 仅在 decoding/kv_cache/sparse 至少一项产出时合入 engine_params。
    """

    smart_decoding_scheme: Optional[str] = None # 投机解码选中方案,如 mtp/eagle3/suffix;未产出 → None
    smart_kv_sparse_scheme: Optional[str] = None # KV 稀疏化选中方案,如 indexcache;未产出 → None
    smart_kv_cache_scheme: Optional[str] = None # KV 卸载选中方案,如 cpu/disk/cpu_disk;未产出 → None
    smart_distributed_kv_cache_scheme: Optional[str] = None # Mooncake standalone-store;未产出 → None
    engine_params: EngineParams = field(default_factory=EngineParams) # 合并后的 env + engine_config;产出侧,无 MaaS 来源
    # KV 内存卸载最终容量(GB,页面回显口径):auto 估算值或数值模式解析值;生效 → int,
    # auto 请求但估算不足被关 → 0(推荐值低于下限),未请求内存卸载(一级关/仅disk) → None。
    # 由 core 从 smart_kv_cache_config(loader 已解析 _memory_capacity_gb)推导,供
    # wings-control 写 advanced_features.json 的 others.kv_mem_offload_size。
    kv_mem_offload_size_gb: Optional[int] = None
    # KV 磁盘卸载实际生效路径;disk_offload_enabled 且 offload 产出时为 str,否则 None。
    # 供 wings-control 在 vllm serve 前渲染残留清理(rm -rf $path/kvcache/*,见 script_builder):
    # 服务重启后 LMCache 落盘的旧 KV 数据会残留并超出 MaaS 规划容量,须启动前清空。
    kv_disk_offload_path: Optional[str] = None
    diagnostics: Dict[str, Dict[str, Any]] = field(default_factory=dict) # 降级诊断;只写 degraded 特性,原样落 audit
    packages: List[str] = field(default_factory=list) # 各选中 scheme 声明的 pip 依赖汇总(name:version);供 install 段 --config
    pre_serve: List[str] = field(default_factory=list) # 聚合:所有节点 pre-serve 命令(去重保序);script_builder 在 vllm serve 前渲染
    pre_serve_master: List[str] = field(default_factory=list) # 聚合:仅 master 的 daemon 启动命令(去重保序);包 RANK_IP==MASTER_IP 条件
    # 聚合:仅 client(非 master)pre-serve 命令(去重保序);包 RANK_IP!=MASTER_IP 条件
    pre_serve_client: List[str] = field(default_factory=list)
    # 非空 pre_serve 三桶的来源:True=包内资产,False=外部资产,None=无命令或来源未知。
    # 由 api.resolve_smart_accel_from_config 根据实际命中的 source_file 填写。
    pre_serve_trusted: Optional[bool] = None
    generated_files: List[GeneratedFile] = field(default_factory=list) # 已渲染、未写盘的文件计划;交由 wings-control 在非 dry-run 产物阶段写入
    # Mooncake 部件来源(四部件 yaml/script_fallback + transfer_engine yaml/injected/disabled),
    # 供审计和运行时日志使用。
    mooncake_component_sources: Dict[str, str] = field(default_factory=dict)
    mooncake_script_assets_required: bool = False # 是否需安装脚本兜底共享卷资产
    # Mooncake master 分支段(early-exit 块的 shell 行);空 → script_builder 不渲染该段。
    mooncake_master_section: List[str] = field(default_factory=list)
    # 传输引擎包("name:version"):distributed_offload 决策的注入/声明结果,供 wings-control
    # 的 master Pod 交付支线渲染只含该包的 install 段(mooncake_master 二进制来源;
    # engine Pod 的 install 段继续用全量 packages,不受此字段影响)。
    # None = 未声明且未注入(ENABLE_XCACHE_INSTALL=false / 特性未启用),镜像预装兜底。
    mooncake_transfer_engine_package: Optional[str] = None
