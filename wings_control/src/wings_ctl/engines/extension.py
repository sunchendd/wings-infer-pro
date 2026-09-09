"""引擎扩展能力的公共协议与延迟注册入口。

公共流水线只通过本模块查询参数翻译、解析后准备、强校验、启动计划和运维
profile。具体引擎可以组合其中一部分能力；未声明的能力继续走现有 argv 引擎默认
路径。协议不定义任何 topology 或 runtime 私有字段，避免特殊引擎的实现细节反向
进入公共层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, List, Mapping, Optional, Tuple

from wings_ctl.core.models import (
    ParamValidationResult,
    PipelineRequest,
    ResolvedConfig,
)
from wings_ctl.core.topology import Topology


Transform = Callable[[dict, dict[str, Any]], tuple[dict, dict]]
PrepareHook = Callable[[ResolvedConfig, PipelineRequest], Any]
ControlPrepareHook = Callable[[ResolvedConfig], None]
Validator = Callable[[ResolvedConfig], ParamValidationResult]


@dataclass(frozen=True)
class EngineLaunchPlan:
    """脚本渲染层消费的最小引擎启动计划。

    ``argv`` 始终交给公共 ScriptBuilder 启动和监督；特殊引擎需要的配置落盘或
    环境准备只能放在 ``pre_start_lines``。``system_setup_source_commands`` 是经过
    引擎命令规格校验后、紧邻 engine argv 执行的 source 环境初始化命令。该模型只
    描述执行协议，不携带 topology 或引擎私有状态，因此渲染层无需按引擎分支。
    """

    argv: List[str]
    pre_start_lines: List[str] = field(default_factory=list)
    system_setup_source_commands: List[str] = field(default_factory=list)
    preview: str = ""
    preview_label: str = "argv"
    preview_on_new_line: bool = False
    repro_trace_lines: Optional[List[str]] = None


@dataclass(frozen=True)
class ParameterTranslationProfile:
    """具名参数的引擎专属改名、丢弃及审计原因。"""

    mapping: Mapping[str, str | None]
    drop_reasons: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HealthProfile:
    """引擎健康端点覆盖；``None`` 表示沿用公共 backend 地址。"""

    host_env: str
    port_env: str
    default_host: str
    default_port: int


@dataclass(frozen=True)
class ProgressProfile:
    """在公共启动阶段表上追加或覆盖的阶段定义。"""

    stage_overrides: Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True)
class EngineExtension:
    """一个引擎可以选择性实现的公共能力集合。

    ``prepare`` 是唯一允许在基础配置解析完成后生成领域状态的入口。其返回值会原样
    保存到 ``ResolvedConfig.engine_state``，公共层不读取其中字段；非法输入必须由
    extension fail-fast，不能退化成另一个 topology 或静默丢弃。

    ``control_prepare`` 在校验完成后、启动产物发布前运行，用于准备 control 与
    engine 之间的共享输入；公共层只调用 hook，仍不读取引擎私有状态。
    """

    # topology 支持范围属于扩展能力契约，而不是某个 CLI 入口的临时判断。公共
    # Pipeline 在进入 ConfigResolver 前统一校验，可防止不支持 PD 的引擎先误入
    # argv/ProcessPlan 构建；None 表示沿用公共层当前支持的全部 topology。
    supported_topologies: Optional[Tuple[Topology, ...]] = None
    parameter_translation: Optional[ParameterTranslationProfile] = None
    post_template_transforms: Optional[Tuple[Transform, ...]] = None
    prepare: Optional[PrepareHook] = None
    # 在 wings-control 中运行，且必须早于启动产物发布。
    control_prepare: Optional[ControlPrepareHook] = None
    validator: Optional[Validator] = None
    launch_builder: Optional[Callable[[ResolvedConfig], EngineLaunchPlan]] = None
    health: Optional[HealthProfile] = None
    progress: Optional[ProgressProfile] = None


@lru_cache(maxsize=None)
def get_engine_extension(engine: str) -> EngineExtension:
    """按规范化引擎名取得扩展，非特殊引擎返回空能力对象。

    MindIE 使用延迟导入，保证 vLLM/SGLang 的启动、校验和健康子进程不会加载其
    schema 与双机实现。新增引擎时只在这里登记唯一装配入口，不在各公共消费者里
    重复比较引擎名称。
    """
    loader = _EXTENSION_LOADERS.get(engine)
    return loader() if loader is not None else EngineExtension()


def _load_mindie_extension() -> EngineExtension:
    """延迟加载 MindIE，避免普通 argv 进程初始化其领域模块。"""
    from wings_ctl.engines.mindie.extension import MINDIE_EXTENSION

    return MINDIE_EXTENSION


# 这是公共层唯一的引擎名称登记点。消费者只查询能力对象，不能复制本表或自行增加
# 名称判断；loader 而非对象本身入表，保持非 MindIE 路径的依赖隔离。
_EXTENSION_LOADERS: Mapping[str, Callable[[], EngineExtension]] = {
    "mindie": _load_mindie_extension,
}
