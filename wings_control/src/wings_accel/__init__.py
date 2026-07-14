"""
wings_accel — SmartAccel 三特性加速模块公共接口。

重要关键点:
- 这是 wings_accel 包的公共导出面,调用方不应依赖各子模块内部细节。
- 主入口 func_smart_accel 消费 SmartAccelInput,返回结构化 engine_config/env/诊断的 SmartAccelOutput。
- resolve_smart_accel_from_config 提供自闭环接口:按入参定位包内/外部 smart-accel YAML 后解析。
- render/yaml_loader 的工具函数也在此导出,便于上层组合与单测复用。
"""
__all__ = [
    "func_smart_accel",
    "resolve_smart_accel_from_config",
    "load_smart_accel_from_yaml",
    "load_smart_accel_from_config",
    "build_smart_accel_yaml_path",
    "find_smart_accel_yaml_path",
    "LoadFlags",
    "PlaceholderContext",
    "render_engine_config",
    "fill_envs",
    "render_scheme",
    "write_scheme_files",
    "deep_merge_dicts",
    "merge_engine_params",
    "SmartAccelInput",
    "SmartAccelOutput",
    "EngineParams",
    "SystemConfig",
    "ModelConfig",
    "EngineConfig",
    "SmartDecodingConfig",
    "SmartKVCacheConfig",
    "SmartKVSparseConfig",
    "DeploymentMode",
]

from wings_accel.api import resolve_smart_accel_from_config
from wings_accel.core import func_smart_accel
from wings_accel.render import (
    PlaceholderContext,
    deep_merge_dicts,
    fill_envs,
    merge_engine_params,
    render_engine_config,
    render_scheme,
    write_scheme_files,
)
from wings_accel.yaml_loader import (
    LoadFlags,
    build_smart_accel_yaml_path,
    find_smart_accel_yaml_path,
    load_smart_accel_from_config,
    load_smart_accel_from_yaml,
)
from wings_accel.schemas import (
    SmartAccelInput,
    SmartAccelOutput,
    EngineParams,
    SystemConfig,
    ModelConfig,
    EngineConfig,
    SmartDecodingConfig,
    SmartKVCacheConfig,
    SmartKVSparseConfig,
    DeploymentMode,
)
