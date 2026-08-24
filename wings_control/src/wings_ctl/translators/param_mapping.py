"""用户具名参数 → 引擎 native 参数。引擎差异通过映射表表达。"""

from __future__ import annotations

from wings_ctl.engines.extension import get_engine_extension

_DROP = ""  # 空串 = 丢弃

# vllm / vllm-ascend 共用:改名集 + 丢弃集均引擎无关
_VLLM = {
    # 改名
    "model_path": "model",
    "model_name": "served_model_name",
    # input/output_length:vllm 无同名 native 参数,本身不渲染(_DROP)。
    #   但它们**已被 cli `_derive_max_model_len` 消费**派生出 max_model_len(= input+output),
    #   并在 user_cli 层覆盖 recipe。故此处只是"原值不进 argv"。
    "input_length": _DROP,
    "output_length": _DROP,
    # 特性开关 toggle:不直接渲染原 key,由 FeatureOverlay 接管。
    #   两者都是"开关";真正参数(--reasoning-parser / --tool-call-parser + --enable-auto-tool-choice)
    #   由小策略层 feature_overlay 从 model.yaml `features` 块拼出。
    #   故此处一律丢弃(不进 user_cli 渲染层);开关状态另经 resolve_config(feature_switches=) 传入。
    "enable_auto_think_choice": _DROP,
    "enable_auto_tool_choice": _DROP,
    # SmartQoS/EnableTrace/Metrics 特性开关:不直接渲染原 key,由 FeatureInject 接管。
    #   开关状态另经 resolve_config(feature_switches=) 传入,真正引擎参数
    #   (--scheduling-policy / --otlp-traces-endpoint / --enable-metrics 等)
    #   由 strategy 层 feature_inject 按引擎类型注入。
    "enable_smartqos": _DROP,
    "enable_otlp_traces": _DROP,
    "enable_metrics": _DROP,
    # 同名直通(不列,缺省返回原 key):host / port / max_num_seqs / max_num_batched_tokens /
    #   trust_remote_code /
    #   dtype / kv_cache_dtype / quantization / quantization_param_path / gpu_memory_utilization /
    #   block_size / seed / enable_chunked_prefill / enable_prefix_caching / enable_expert_parallel。
    # 上列原"删掉(不覆盖recipe基线)"一组改为同名直通: user_cli 是最高优先级,
    # 可覆盖 recipe(用户显式传即生效,出错由用户负责)。它们都是 vllm 原生同名参数。
    # 注:quantization / enable_prefix_caching / enable_expert_parallel 在本映射层具备同名直通能力,
    #   但它们当前不在 MAAS_CONTRACT_ALLOWLIST(见下方定义);因此在进入 user_cli merge 之前就被
    #   filter_maas_contract_overrides warn-only dropped,实际不进 argv。若未来 MaaS contract
    #   扩展、将它们补进 allowlist,本处直通才会生效。
}

# sglang:具名 CLI → sglang native(目标名已用 supported_params.txt 核对)。
# recipe 键(tp / dtype / max_total_tokens 等)由 recipe 作者写 sglang 原生名,不经本表。
_SGLANG = {
    # 改名
    "model_path": "model",                   # 归一 canonical 键 "model";渲染形态由命令规格定(sglang --model-path)
    "model_name": "served_model_name",       # --served-model-name
    "max_model_len": "context_length",       # input+output 派生值落点;--context-length
    "max_num_seqs": "max_running_requests",  # --max-running-requests
    "max_num_batched_tokens": "chunked_prefill_size",  # --chunked-prefill-size
    "gpu_memory_utilization": "mem_fraction_static",   # --mem-fraction-static
    "seed": "random_seed",                   # --random-seed
    # 丢弃(sglang 无对应 / 已被派生消费 / 特性开关另接管)
    "input_length": _DROP,                   # 已派生 max_model_len→context_length
    "output_length": _DROP,
    "enable_auto_think_choice": _DROP,       # → FeatureOverlay(同 vllm)
    "enable_auto_tool_choice": _DROP,
    "enable_smartqos": _DROP,                # → FeatureInject(引擎感知注入)
    "enable_otlp_traces": _DROP,
    "enable_metrics": _DROP,
    "enable_chunked_prefill": _DROP,         # sglang 靠 chunked_prefill_size,无独立开关
    "block_size": _DROP,                     # sglang 无 block_size 概念
    # 同名直通(不列):host / port / trust_remote_code
}

_PARAM_MAPPING = {"vllm": _VLLM, "vllm-ascend": _VLLM, "sglang": _SGLANG}

# 当前正式交互参数(canonical engine_config keys)。
# 职责:决定参数是否有资格进入 user_cli merge(与 param_mapping 改名/丢弃职责分离)。
MAAS_CONTRACT_ALLOWLIST = frozenset(
    {
        "host",
        "port",
        "model_path",
        "model_name",
        "max_num_seqs",
        "max_num_batched_tokens",
        "input_length",
        "output_length",
        "max_model_len",
        "trust_remote_code",
        "enable_auto_think_choice",
        "enable_auto_tool_choice",
        "enable_smartqos",
        "enable_otlp_traces",
        "enable_metrics",
        "dtype",
        "kv_cache_dtype",
        "quantization_param_path",
        "gpu_memory_utilization",
        "block_size",
        "seed",
        "enable_chunked_prefill",
    }
)

_DROP_REASONS = {
    # 选填但丢弃: vllm 无对应
    "input_length": "maas_status=原值不入argv;已消费为 max_model_len(=input+output)派生值",
    "output_length": "maas_status=原值不入argv;已消费为 max_model_len(=input+output)派生值",
    # 特性开关不作 user_cli 直通参数:开关状态另经 feature_switches 传入,
    # 真正的引擎参数由 FeatureOverlay 按 model.yaml features 配置渲染。
    "enable_auto_think_choice": "maas_status=开关由 FeatureOverlay 按 model.yaml features 配置渲染,不作 user_cli 直通参数",
    "enable_auto_tool_choice": "maas_status=开关由 FeatureOverlay 按 model.yaml features 配置渲染,不作 user_cli 直通参数",
    "enable_smartqos": "maas_status=开关由 FeatureInject 按引擎类型注入引擎参数,不作 user_cli 直通参数",
    "enable_otlp_traces": "maas_status=开关由 FeatureInject 按引擎类型注入引擎参数,不作 user_cli 直通参数",
    "enable_metrics": "maas_status=开关由 FeatureInject 按引擎类型注入引擎参数,不作 user_cli 直通参数",
}


def translate(key: str, engine: str) -> str | None:
    """按扩展能力或公共映射表执行改名、直通和丢弃。"""
    profile = get_engine_extension(engine).parameter_translation
    if profile is not None and key in profile.mapping:
        return profile.mapping[key]
    mapped = _PARAM_MAPPING.get(engine, {}).get(key, key)  # 缺省同名直通
    return None if mapped == _DROP else mapped  # 空串=丢弃→None


def drop_reason(key: str, engine: str) -> str | None:
    """返回被丢弃参数的审计原因。"""
    profile = get_engine_extension(engine).parameter_translation
    if profile is not None and key in profile.mapping:
        if profile.mapping[key] is not None:
            return None
        return profile.drop_reasons.get(key, "maas_status=丢弃")
    mapped = _PARAM_MAPPING.get(engine, {}).get(key, key)
    if mapped != _DROP:
        return None
    return _DROP_REASONS.get(key, "maas_status=丢弃")
