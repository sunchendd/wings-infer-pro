"""核心数据模型 — ResolvedConfig / TracedValue / SourceEvent / SystemSetup。

全仓库唯一 ResolvedConfig 定义。trace-first: 每个参数的最终值必须可追踪。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from wings_ctl.accel.smart_accel import AccelResult
from wings_ctl.core.topology import Topology

# PD 策略是 exact recipe 与运行时规划器之间的闭集契约。常量供运行时比较，
# 对应的 Literal 供类型检查；新增取值时必须同步 recipe 归一化、运行时校验和测试。
PD_TOPOLOGY_DERIVED_1P1D = "derived_1p1d"  # 六字段缺失，由当前 Pod 卡数派生普通 1P1D。
PD_TOPOLOGY_EXPLICIT_ALLOCATION = "explicit_allocation"  # MaaS 六字段完整下发显式拓扑。
PD_PROCESS_LAYOUT_SINGLE = "single_process"  # 当前 Pod 只生成一条引擎命令。
PD_PROCESS_LAYOUT_PER_LOCAL_RANK = "per_local_dp_rank"  # 每个 local DP rank 生成一条命令。
PD_DP_LAUNCH_NONE = "none"  # 命令不携带外部 DP rank 参数。
PD_DP_LAUNCH_EXTERNAL_RANK = "external_rank"  # 每条命令显式携带自己的 global DP rank。
PD_ENDPOINT_PER_PROCESS = "per_process"  # 每条引擎命令拥有独立 API endpoint。
PD_ENGINE_ID_OMIT = "omit"  # connector 命令不生成 engine_id。
PD_ENGINE_ID_FROM_INDEX = "from_pd_index"  # connector engine_id 取 logical Instance 的 PD_INDEX。
PD_KV_PORT_FROM_INDEX = "from_pd_index"  # KV port 由 base、PD_INDEX 和本地进程序号确定。
PD_KV_LISTENER_SINGLE = "single"  # KV listener 只占用计算出的单个端口。
PD_KV_LISTENER_DEVICE_COUNT_PLUS_ONE = "device_count_plus_one"  # 按 connector 约定预留闭区间。
PD_LISTENER_OWNER_PER_PROCESS = "per_process"  # 当前 Pod 的每个进程各自登记 KV listener。
PD_LISTENER_OWNER_PER_POD_CONNECTOR_GROUP = "per_pod_connector_group"  # 同 Pod connector 组只登记一次。

PdTopologyInputPolicy = Literal["derived_1p1d", "explicit_allocation"]
PdProcessLayout = Literal["single_process", "per_local_dp_rank"]
PdDpLaunchPolicy = Literal["none", "external_rank"]
PdEndpointPolicy = Literal["per_process"]
PdEngineIdPolicy = Literal["omit", "from_pd_index"]
PdKvPortMode = Literal["from_pd_index"]
PdKvListenerSpan = Literal["single", "device_count_plus_one"]
PdListenerOwnerScope = Literal["per_process", "per_pod_connector_group"]


@dataclass(frozen=True)
class SourceEvent:
    """记录一次配置值的写入/覆盖事件。"""

    action: str  # "set" | "override" | "remove"
    # 合并层名(低→高优先):builtin_default / default_model / model_scenario / user_cli,
    # 以及策略层 strategy_device_count / strategy_feature / strategy_accel /
    # strategy_multinode_dp / strategy_topology_inject。
    # 完整层序见 config_resolver._merge_engine_config_traces。
    layer: str
    value: Any
    source_file: str  # 来源文件的相对或绝对路径
    source_path: str  # YAML 路径,如 "scenarios.standalone.strategies.single_node.engine_config.host"


@dataclass
class TracedValue:
    """一个配置参数的完整追踪记录。"""

    final_value: Any
    final_layer: str  # 最终胜出的层
    source_file: str  # 胜出层的文件路径
    source_path: str  # 胜出层的 YAML path
    events: List[SourceEvent] = field(default_factory=list)
    # env 专用:值为 True 时,渲染层跳过 _validate_dollar_value 安全校验,双引号放行 $(...)。
    # 仅 config_file_env 层构造时置 True(用户对自己的输入负责);其余层保持默认 False 不变。
    # 见 rendering/env_renderer.render_env_export 与 script_builder._render_env_section。
    allow_unsafe: bool = False


@dataclass
class HardwareContext:
    """硬件环境信息(由 HardwareResolver 产出)。"""

    hardware_family: str  # 下发原值,目录定位用,如 "h200" / "H100_80G" / "Ascend910B_64G"
    device: str  # "nvidia" | "ascend"
    raw: Dict[str, Any] = field(default_factory=dict)  # 原始 JSON 全量,携带进 audit
    # 单卡显存 GB,取自 hardware_family 的 _<N>G 后缀(单卡物理显存);无后缀则 None。
    # 唯一消费方 = 单机 TP 收缩显存闸;非收缩路径不读,None 无影响。
    # 置于 raw 之后:保持 HardwareContext(family, device, raw) 位置构造兼容。
    gpu_mem_gb: Optional[int] = None


@dataclass
class EngineVersion:
    """引擎版本解析结果。"""

    requested: Optional[str]  # 用户通过 ENGINE_VERSION 设置的原始值
    resolved: str  # 实际使用的版本 (可能是 latest 回退)
    is_fallback: bool  # 是否发生了回退
    has_version_dir: bool = False  # 引擎目录是否使用 vX.Y.Z 版本层


@dataclass(frozen=True)
class Target:
    """解析目标:定位一次部署解析的三要素。

    Attributes:
        model_name: 模型名(用于 name_pattern / variant_name 匹配)。
        topology: 部署拓扑(standalone / multi_node)。
        engine: 引擎名(如 "vllm" / "vllm-ascend" / "sglang")。
    """

    model_name: str
    topology: Topology = Topology.STANDALONE
    engine: str = "vllm"


@dataclass(frozen=True)
class UserInput:
    """用户 CLI 意图:进入 user_cli 合并层的覆盖参数 + 特性开关。

    Attributes:
        cli_overrides: 已翻译为引擎参数名的 user_cli 覆盖层。
        cli_dropped: cli_overrides 的丢弃互补半(同次 translate_overrides 产出的被丢弃项,
            含 key/value/reason),与 cli_overrides 一起拼成完整 user_cli 审计。
        feature_switches: 已开启的特性开关 dict(如 {"enable_auto_tool_choice": True})。
    """

    cli_overrides: Optional[Dict[str, Any]] = None
    cli_dropped: Optional[List[Dict[str, Any]]] = None
    feature_switches: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ClusterPlacement:
    """分布式集群寻址:本 Pod / 全集群 / master 的运行时 IP。

    仅分布式拓扑(multi_node + PD 分离)使用;单机 / 无运行时上下文时整个 placement 为 None。
    名字拓扑无关(不叫 MultiNodePlacement),便于 multi_node 与 PD 复用同一概念。

    Attributes:
        rank_ip: 本 Pod IP(multi_node 选 node 用)。
        node_ips: 全集群节点 IP 列表(决定集群规模与 index)。
        master_ip: master IP(判定 head 并替换占位符)。
    """

    rank_ip: Optional[str] = None
    node_ips: Optional[List[str]] = None
    master_ip: Optional[str] = None


class PdRole(Enum):
    """PD 引擎角色。"""

    PREFILL = "P"
    DECODE = "D"


@dataclass(frozen=True)
class ParallelShape:
    """一个 logical Instance 的并行形状。"""

    dp_size: int
    tp_size: int


@dataclass(frozen=True)
class ExplicitPdTopology:
    """MaaS 原子下发的大 EP topology。

    Attributes:
        pd_index: logical Instance 在 P 在前、D 在后顺序中的全局序号。
        prefill: 所有 P Instance 共用的 global DP/TP 形状。
        decode: 所有 D Instance 共用的 global DP/TP 形状。
        dp_size_local: 当前 role 每个成员 Pod 承载的 local DP rank 数。
    """

    pd_index: int
    prefill: ParallelShape
    decode: ParallelShape
    dp_size_local: int


@dataclass(frozen=True)
class PdRuntimeInput:
    """规范化后的当前 Pod PD 输入。

    Attributes:
        role: 当前 Pod 的 P/D 角色。
        explicit_topology: 六字段全存在时的显式 topology；全缺失时为 ``None``。
        placement: 当前 logical Instance 的有序成员位置。
    """

    role: PdRole
    explicit_topology: Optional[ExplicitPdTopology]
    placement: ClusterPlacement


@dataclass(frozen=True)
class KvPortPolicy:
    """Exact connector profile 的 KV listener 派生规则。

    Attributes:
        mode: KV port 的闭集计算策略。
        listener_span: 从计算出的 KV port 起需要登记的 listener 区间规则。
        base: 第一个 logical Instance 的 KV port。
        instance_stride: 相邻 logical Instance 的 KV port 步长。
        process_stride: 同一 Pod 相邻本地进程的 KV port 步长。
    """

    mode: PdKvPortMode
    listener_span: PdKvListenerSpan
    base: Optional[int] = None
    instance_stride: int = 0
    process_stride: int = 0


@dataclass(frozen=True)
class ConnectorProfile:
    """Exact recipe 冻结的 connector identity 与 listener 策略。

    Attributes:
        connector_name: recipe 中已验收的 KV connector 名称。
        engine_id_policy: 是否生成 engine_id，以及它与 PD_INDEX 的关系。
        kv_port_policy: KV port 与预留区间的派生规则。
        listener_owner_scope: KV listener 按进程登记还是按 Pod connector 组登记。
    """

    connector_name: str
    engine_id_policy: PdEngineIdPolicy
    kv_port_policy: KvPortPolicy
    listener_owner_scope: PdListenerOwnerScope


@dataclass(frozen=True)
class PdRuntimeSpec:
    """从 exact nodes recipe 归一化的固定 PD 规划元数据。

    这里保存 recipe 已经确定、但不应直接留在静态 engine_config 中的执行策略。planner
    只消费这些闭集值，不根据模型名或硬件重新选择并行方案。

    Attributes:
        topology_input_policy: 接受普通 1P1D 派生输入或 MaaS 显式 topology。
        prefill_shape: recipe 验收的 P global DP/TP 形状。
        decode_shape: recipe 验收的 D global DP/TP 形状。
        instance_member_count: 当前 role 每个 logical Instance 固定包含的 Pod 数。
        process_layout: 当前 Pod 内引擎进程如何展开。
        dp_launch_policy: 是否由每条命令显式携带 external DP rank。
        endpoint_policy: backend endpoint 与进程的对应规则。
        backend_port_base: 当前 Pod 第一条引擎命令使用的 API backend port。
        data_parallel_rpc_port: logical Instance 的 DP 协调端口；普通单进程 PD 为 ``None``。
        connector_profile: engine_id、KV port 和 listener owner 的固定策略。
    """

    topology_input_policy: PdTopologyInputPolicy
    prefill_shape: ParallelShape
    decode_shape: ParallelShape
    instance_member_count: int
    process_layout: PdProcessLayout
    dp_launch_policy: PdDpLaunchPolicy
    endpoint_policy: PdEndpointPolicy
    backend_port_base: int
    data_parallel_rpc_port: Optional[int]
    connector_profile: ConnectorProfile


@dataclass(frozen=True)
class ResolvedPdTopology:
    """Recipe 匹配并完成本 Pod 强校验后的 PD topology。

    Attributes:
        input_policy: 实际采用的 topology 输入策略。
        role: 当前 Pod 是 Prefill 还是 Decode。
        instance_index: 当前 logical Instance 的 PD_INDEX；普通 1P1D 固定 P=0、D=1。
        prefill: 已闭合的 P global DP/TP 形状。
        decode: 已闭合的 D global DP/TP 形状。
        dp_size_local: 当前 Pod 要展开的 local DP rank 数。
        placement: 当前 Instance 的 master、成员顺序和本 Pod IP。
        member_index: 当前 Pod 在 ``placement.node_ips`` 中的位置。
        rank_start: 当前 Pod 第一个 global DP rank。
        rank_end_exclusive: 当前 Pod global DP rank 半开区间的右边界。
    """

    input_policy: PdTopologyInputPolicy
    role: PdRole
    instance_index: int
    prefill: ParallelShape
    decode: ParallelShape
    dp_size_local: int
    placement: ClusterPlacement
    member_index: int
    rank_start: int
    rank_end_exclusive: int


@dataclass(frozen=True)
class ListenerPlan:
    """本 Pod 可静态验证的 listener 或预留区间。

    该对象用于冲突检查和审计，不执行 socket bind。

    Attributes:
        name: listener 类型，例如 API、DP RPC 或 KV。
        host: 计划 bind 或接受连接的地址。
        port_start: 预留区间起点；未知时为 ``None``。
        port_end: 预留区间终点，区间两端都包含。
        owner: 拥有该 listener 的进程或共享 connector 组。
        status: 计划状态；当前只生成 ``planned``。
    """

    name: str
    host: str
    port_start: Optional[int]
    port_end: Optional[int]
    owner: str
    status: str = "planned"


@dataclass
class EngineProcessPlan:
    """一条 engine 启动命令的最终结构化执行计划。

    PD 的一个 Pod 可以启动多条 ``vllm serve``。每个对象只描述其中一条命令，渲染、
    参数校验和审计都应消费这里的 per-process trace/argv，不能回退读取 Pod 顶层 trace。

    Attributes:
        process_index: 当前 Pod 内稳定的进程顺序，同时决定脚本中的启动顺序。
        local_index: 当前 Pod 内 local DP rank 序号；目前与 ``process_index`` 相同，
            单独保留以表达 DP 语义。
        dp_rank: logical Instance 内 global DP rank；普通单进程 PD 不启用 external DP 时为
            ``None``。
        visible_devices: 分配给该进程的 Pod 内设备序号切片。
        advertised_endpoint: 路由层访问该进程的 ``RANK_IP:backend_port``。
        engine_config_traces: 该进程最终 engine 参数及完整来源事件。
        env_traces: 该进程最终环境变量及完整来源事件。
        argv: 由 ``engine_config_traces`` 渲染出的结构化启动参数。
        listeners: 该进程拥有或代表的 API、DP RPC、KV listener 计划。
        param_validation: 该进程的引擎参数 warn-only 校验结果。
    """

    process_index: int
    local_index: int
    dp_rank: Optional[int]
    visible_devices: tuple[int, ...]
    advertised_endpoint: Optional[str]
    engine_config_traces: Dict[str, TracedValue]
    env_traces: Dict[str, TracedValue]
    argv: List[str]
    listeners: List[ListenerPlan] = field(default_factory=list)
    param_validation: Optional[ParamValidationResult] = None


@dataclass
class ProcessPlan:
    """当前 Pod 的有序 engine process 集合，也是 PD 渲染与审计的真相源。

    Attributes:
        layout: exact recipe 归一化出的进程布局，例如单进程或每 local DP rank 一进程。
        lifecycle: 多进程失败联动策略；``fail_together`` 表示任一进程退出时整组退出。
        processes: 按 local rank 排序的最终进程计划。
        endpoints: 与 ``processes`` 同序的对外 backend endpoint。
        listeners: 当前 Pod 汇总后的 listener inventory，用于端口冲突校验和审计。
    """

    layout: str
    lifecycle: str
    processes: List[EngineProcessPlan]
    endpoints: List[str]
    listeners: List[ListenerPlan] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineRequest:
    """一次流水线解析的完整请求(调用方提供的输入,hardware/version 尚未解析)。

    Attributes:
        target: 解析目标(模型/拓扑/引擎)。
        hardware_info_path: hardware_info.json 路径。
        config_root: 配置资产根 —— **裸待解析入参**(None=自动定位);
            解析后的真实根见 ResolvedEnv.config_root(勿混淆二者的生命周期)。
        user_input: 用户 CLI 意图。
        device_count: 下发卡数(全程规模:单机驱动 DP、多机参与协调;None=不触发)。
        placement: multi_node 或 PD 的集群寻址;单机/无运行时上下文为 None。
        pd_input: PD 当前 Pod 的原子输入；标准推理为 None。
        pd_role_missing_legacy: ``PD_ROLE`` 完全缺失时的迁移标记；仅写入解析说明，
            不把标准推理改判为 PD。
    """

    target: Target
    hardware_info_path: Path
    config_root: Optional[Path] = None
    user_input: UserInput = UserInput()
    device_count: Optional[int] = None
    placement: Optional[ClusterPlacement] = None
    pd_input: Optional[PdRuntimeInput] = None
    pd_role_missing_legacy: bool = False


@dataclass(frozen=True)
class CustomConfigFile:
    """自定义传参方式(--config-file)的已加载产物。

    `params` 为引擎原生参数(用户自管,不做字段映射,仅 snake_case 归一);
    `env` 为用户自定义环境变量(值可含 ``$(hostname)`` 等 shell 构造,渲染时放行)。
    两字段可选;同时为空时等价于未传 --config-file(分派层不必进 custom 路径)。
    """
    params: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedEnv:
    """已解析的环境:hardware / engine_version 算完后交给 resolve_config 的三要素。

    Attributes:
        config_root: **已定位的真实配置根**(解析结果绝对路径;
            区别于 PipelineRequest.config_root 的裸待解析入参)。
        hardware: 解析出的硬件上下文。
        engine_version: 解析出的引擎版本(含 latest 回退信息)。
    """

    config_root: Path
    hardware: HardwareContext
    engine_version: EngineVersion


@dataclass
class SystemSetup:
    """系统级设置(sysctl / sysfs / commands)。

    仅记录+渲染(注释形式),框架不执行。
    默认从空集合开始,不从 _platform.yaml 预置。
    """

    sysctls: Dict[str, Any] = field(default_factory=dict)
    sysfs_writes: List[Dict[str, str]] = field(default_factory=list)
    # 所有拓扑均按注释形式渲染 commands，框架不执行其中命令。
    commands: List[str] = field(default_factory=list)
    source_file: str = ""  # 来源文件(用于 audit)
    source_path: str = ""  # YAML 路径


@dataclass
class ResolvedNode:
    """multi_node 场景下单个节点(=Pod)的解析结果。

    每个 node 独立持有自己那份 engine_config / env 的 trace + system_setup。
    无运行时上下文时,字面占位符按 YAML 原值保留，
    ``ResolvedConfig.nodes`` 承载全集群视图并产出占位脚本。
    运行时上下文完整时,会选出本 Pod 节点升为顶层可执行配置；
    通信 IP 和网卡变量由网络后置策略解析为本 Pod 的实际值。

    Attributes:
        role: 节点角色(``head`` / ``worker``;PD 为 ``prefill`` / ``decode``)。
        index: 节点序号(recipe 显式给出时;multi_node 通常 None)。
        engine_config_traces: 本节点 engine_config 的逐参 trace(已深合并 builtin/user_cli)。
        env_traces: 本节点 env 的逐项 trace。
        system_setup: 本节点系统级设置。
        source_prefix: 本节点 yaml 路径前缀(如 ``...nodes[0]``),供 audit 溯源。
    """

    role: str
    index: Optional[int]
    engine_config_traces: Dict[str, "TracedValue"]
    env_traces: Dict[str, "TracedValue"]
    system_setup: Optional["SystemSetup"] = None
    source_prefix: str = ""


@dataclass
class ParamValidationResult:
    """EngineParamValidator 校验结果 — warn-only,只记录不改参。

    Attributes:
        policy: 恒 ``"warn_only"``(记录用;runtime 绝不删参/不 fail)。
        supported_params_file: 命中的 ``supported_params.txt`` 路径;``None``=未找到/跳过。
        status: ``"checked"``(已比对清单)| ``"skipped_missing_file"``(缺/空清单,warn-skip 兜底)。
        unsupported: would-warn 参数列表,每项含
            ``param`` / ``rendered_as`` / ``final_layer`` / ``source_file`` / ``source_path``。
    """

    policy: str = "warn_only"
    supported_params_file: Optional[str] = None
    status: str = "checked"
    unsupported: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ResolvedConfig:
    """配置解析最终产物 — 全仓库唯一定义。

    包含 engine_config_traces / env_traces / source_files / topology。
    """

    topology: Topology
    hardware: HardwareContext
    engine: str  # "vllm"
    engine_version: EngineVersion

    engine_config_traces: Dict[str, TracedValue]  # 参数名 → TracedValue
    env_traces: Dict[str, TracedValue]  # 环境变量名 → TracedValue
    source_files: List[str]  # 参与合并的所有源文件

    # 系统级设置(仅来自模型场景层,不预置)
    system_setup: Optional[SystemSetup] = None

    # 解析过程中产生的注记(如 "platform_default": "absent")
    resolution_notes: Dict[str, str] = field(default_factory=dict)

    # user_cli 参数审计(包含 dropped 条目,供 audit.json 展示)
    user_cli_params: List[Dict[str, Any]] = field(default_factory=list)

    # config-file 参数审计(自定义传参方式):applied(config_file_params)+ dropped
    # (黑名单弃置项)。仅走 resolve_custom_config 时非空;默认空列表 → audit 不写该键。
    config_file_params: List[Dict[str, Any]] = field(default_factory=list)

    # multi_node 占位视图:无运行时上下文时承载全集群 per-node 解析,
    # 顶层 engine_config_traces/env_traces 为空(不伪造单 Pod 视图),build_scripts 走占位路径。
    # 选出本 Pod 节点后 nodes 置 None(本 Pod 升为顶层可执行)。standalone 恒 None。
    nodes: Optional[List["ResolvedNode"]] = None

    # wings-accel(智能加速)产出:由 apply_smart_accel 填充。engine_config 已作为 strategy_accel
    # 合并层并入 engine_config_traces(不再末尾 append);本字段仅余 env(渲染 export 段)、
    # audit(写 scheme)、enabled(install 段门控)。默认空 AccelResult → 零影响(模块未接通时 no-op)。
    accel: AccelResult = field(default_factory=AccelResult)

    # EngineParamValidator 结果:合并/accel 后校验最终参数集(warn-only,不改参)。
    # None=未校验(validator 未接通);standalone/multi_node 均由 validate_engine_params 填充
    # (run_pipeline 与 cli dry-run 两路径一致)。
    param_validation: Optional[ParamValidationResult] = None

    # PD 可执行配置只存在于 process_plan；标准推理两字段恒 None，继续使用顶层 traces。
    pd_topology: Optional[ResolvedPdTopology] = None
    process_plan: Optional[ProcessPlan] = None
