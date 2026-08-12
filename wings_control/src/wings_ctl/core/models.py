"""核心数据模型 — ResolvedConfig / TracedValue / SourceEvent / SystemSetup。

全仓库唯一 ResolvedConfig 定义。trace-first: 每个参数的最终值必须可追踪。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from wings_ctl.accel.smart_accel import AccelResult
from wings_ctl.core.topology import Topology


@dataclass(frozen=True)
class SourceEvent:
    """记录一次配置值的写入/覆盖事件。"""

    action: str  # "set" | "override"
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

    仅分布式拓扑(multi_node + 未来 PD 分离)使用;单机 / 无运行时上下文时整个 placement 为 None。
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
    """MaaS 原子下发的场景 B topology。"""

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
    """Exact connector profile 的 KV listener 派生规则。"""

    mode: str
    listener_span: str
    base: Optional[int] = None
    instance_stride: int = 0
    process_stride: int = 0


@dataclass(frozen=True)
class ConnectorProfile:
    """Exact recipe 冻结的 connector identity 与 listener 策略。"""

    connector_name: str
    engine_id_policy: str
    kv_port_policy: KvPortPolicy
    listener_owner_scope: str


@dataclass(frozen=True)
class PdRuntimeSpec:
    """从 exact nodes recipe 归一化的固定 PD 规划元数据。"""

    topology_input_policy: str
    prefill_shape: ParallelShape
    decode_shape: ParallelShape
    instance_member_count: int
    process_layout: str
    dp_launch_policy: str
    endpoint_policy: str
    backend_port_base: int
    data_parallel_rpc_port: Optional[int]
    connector_profile: ConnectorProfile


@dataclass(frozen=True)
class ResolvedPdTopology:
    """Recipe 匹配并完成本 Pod 强校验后的 PD topology。"""

    input_policy: str
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
    """本 Pod 可静态验证的 listener 或预留区间。"""

    name: str
    host: str
    port_start: Optional[int]
    port_end: Optional[int]
    owner: str
    status: str = "planned"


@dataclass
class EngineProcessPlan:
    """一个最终 engine process 的结构化执行计划。"""

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
    """当前 Pod 的有序 engine process 集合。"""

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
        placement: 分布式集群寻址(仅 multi_node;单机/无运行时上下文为 None)。
        pd_input: PD 当前 Pod 的原子输入；标准推理为 None。
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
    # standalone 路径按注释渲染;multi_node 已注入路径会 inline 执行其中的运行时命令。
    commands: List[str] = field(default_factory=list)
    source_file: str = ""  # 来源文件(用于 audit)
    source_path: str = ""  # YAML 路径


@dataclass
class ResolvedNode:
    """multi_node 场景下单个节点(=Pod)的解析结果。

    每个 node 独立持有自己那份 engine_config / env 的 trace + system_setup。
    无运行时上下文时,占位符 ``$node0_ip`` / ``$local_ip`` / ``$nic_name`` 按字面保留,
    ``ResolvedConfig.nodes`` 承载全集群视图并产出占位脚本。
    运行时上下文完整时,会选出本 Pod 节点升为顶层可执行配置,
    占位由 ``system_setup.commands`` 在运行时填充(见 ``strategy.topology_inject``)。

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
