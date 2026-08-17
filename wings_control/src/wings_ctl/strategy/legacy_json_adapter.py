"""FOAI 旧版前端自定义 JSON 模板 → 新版 custom(--config-file)路径的过渡适配层。

背景:
    新版 wings-infer 自定义传参(config-file)已与常规配置传参拆成两条独立分支
    (resolve_custom_config)。但 FOAI 前端还在用**旧版**自定义 JSON 模板:
    - 参数键为旧版形态(自带 `input-length`/`output-length` 等业务键),
    - 不传 `tensor-parallel-size`(需默认补上 = device_count),
    - 部分旧版键在 vllm/sglang 之间不能通用映射,需按引擎映射或丢弃。

    本模块做**临时过渡**:把旧版模板适配成新版 custom 参数,兼容 FOAI 旧前端。
    过渡完成后本模块连同调用点应直接删除,因此刻意与 config_resolver 的解析骨干解耦
    ——只在 resolve_custom_config 里 config-file 解析后的单点被调用,不侵入既有
    merge/黑名单/canonical 机制。

核心理念(用户拍板):
    ``adapt_legacy_config_params`` 的**产出 = "用户直接传的新版参数"**。适配层唯一要做的是
    把旧模板形态翻译成新版权威键形态;之后下游模块(canonical / 黑名单 / merge / 派生层)
    就当它是用户直接传的参数处理,完全不感知它"来自旧模板"。**所有参数**都遵循这一理念:

    - **透传** = 键本身就是该引擎的新版权威键 → 原样保留(等价于用户传它)。
    - **映射** = 旧版键翻译成该引擎权威键 → 翻译后等价于用户传了权威键,旧键不残留。
    - **丢弃** = 该引擎下无意义的旧键(非权威/非原生)→ 直接移除,不留残余。
    - **补默认** = 旧模板未填某权威键 → 生成默认(等价于用户传了该键)。

    因此产出应是**干净的新版权威键集合**,下游不感知旧模板的存在。

处理约束:
    - 只对旧模板已知键做映射/丢弃/默认;用户基于模板**添加的任何参数一律直接透传**
      (不映射不丢弃;不采用白名单/黑名单式兜底,以免误丢用户自定义参数)。
    - input-length/output-length 只是"算出权威长度键"的派生源,**不直接成为引擎参数**,
      适配后总是被消费/丢弃,不残留。权威长度键优先(见 :func:`_merge_length` )。
    - 不涉及 recipe yaml。

Args 约定见 :func:`adapt_legacy_config_params`。
"""

from __future__ import annotations

from typing import Any, Dict, List

_ENGINES = ("vllm", "vllm-ascend", "sglang")

# 引擎 → 权威长度键。
# vllm/vllm-ascend 用 max_model_len(--max-model-len);sglang 用 context_length(--context-length)。
_AUTHORITATIVE_LEN_KEY: Dict[str, str] = {
    "vllm": "max_model_len",
    "vllm-ascend": "max_model_len",
    "sglang": "context_length",
}

# sglang:旧模板键 → sglang 原生键(映射;等价于用户传该权威键)。
_SGLANG_RENAME: Dict[str, str] = {
    "max_num_seqs": "max_running_requests",
    "max_num_batched_tokens": "chunked_prefill_size",
    "gpu_memory_utilization": "mem_fraction_static",
    "seed": "random_seed",
}

# vllm / vllm-ascend:旧模板已知键里可透传的(vllm 原生);未列出 → 丢弃。
_VLLM_TRANSPARENT: frozenset = frozenset({
    "trust_remote_code",
    "dtype",
    "kv_cache_dtype",
    "gpu_memory_utilization",
    "enable_chunked_prefill",
    "block_size",
    "max_num_seqs",
    "max_num_batched_tokens",
    "seed",
    "enable_expert_parallel",
    "enable_prefix_caching",
    "enable_auto_tool_choice",
})

# sglang:旧模板已知键里可透传的(sglang 原生);未列出 → 丢弃。
_SGLANG_TRANSPARENT: frozenset = frozenset({
    "trust_remote_code",
    "dtype",
    "kv_cache_dtype",
})

# 旧模板业务键:不直接成为引擎参数,只作推导源/丢弃。
_LEGACY_LEN_KEYS = ("input_length", "output_length")

# 旧模板已知键全集(不含 input/output-length——由 _merge_length 单独处理)。
# 仅此集合内的键会被本适配层映射/透传/丢弃;集合之外的任何键(用户添加)一律透传。
_LEGACY_KEYS: frozenset = frozenset({
    "trust_remote_code",
    "dtype",
    "kv_cache_dtype",
    "gpu_memory_utilization",
    "enable_chunked_prefill",
    "block_size",
    "max_num_seqs",
    "max_num_batched_tokens",
    "seed",
    "enable_expert_parallel",
    "enable_prefix_caching",
    "enable_auto_tool_choice",
    "enable_auto_think_choice",
})


def _merge_length(
    params: Dict[str, Any],
    adapted: Dict[str, Any],
    dropped: List[Dict[str, Any]],
    *,
    engine: str,
) -> None:
    """长度键处理(核心理念:产出 = 用户直接传权威长度键)。

    权威长度键 = vllm/ascend ``max_model_len``、sglang ``context_length``。

    - **已填权威长度键** → 透传(等价于用户传它),并丢弃 input/output-length 源。
    - **未填权威长度键**,但填了 input/output-length(至少一侧)→ 生成权威长度键
      = ``input_length + output_length``(缺失侧记 0),丢弃两个 length 键;等价于用户传了
      权威长度键 = input+output。
    - **未填权威长度键,且 input/output 都未填** → 跳过,不生成。
    - **对侧长度键**(vllm 填 ``context_length``、sglang 填 ``max_model_len``)→ 属用户自添
      参数,由外层透传(不在此处理),引擎报错兜底、用户对参数负责。
    """
    target = _AUTHORITATIVE_LEN_KEY.get(engine)
    if target is None:
        return

    # 已填权威长度键 → 透传(外层主循环会透传,非旧模板键);此处只需保证丢弃 length 源。
    if target in params:
        # 权威长度键本身由外层透传(不在 _LEGACY_KEYS 内 → 用户添加键透传)。
        _drop_legacy_len_sources(params, adapted, dropped)
        return

    # 未填权威长度键:用 input/output-length 生成(至少一侧在)。
    present = [k for k in _LEGACY_LEN_KEYS if k in params]
    if not present:
        return  # input/output 都未填 → 跳过

    total = 0
    for k in _LEGACY_LEN_KEYS:
        v = params.get(k, 0)  # 缺失侧记 0
        if isinstance(v, int):
            total += v
    adapted[target] = total
    _drop_legacy_len_sources(params, adapted, dropped)


def _drop_legacy_len_sources(
    params: Dict[str, Any],
    adapted: Dict[str, Any],
    dropped: List[Dict[str, Any]],
) -> None:
    """把输入里的 input/output-length 从 adapted 中移除(不残留),并记审计丢弃项。"""
    for k in _LEGACY_LEN_KEYS:
        if k in params:
            adapted.pop(k, None)
            dropped.append({
                "key": k, "value": params[k],
                "reason": "legacy_json_adapter=旧 length 业务键,已折算进权威长度键",
            })


def adapt_legacy_config_params(
    params: Dict[str, Any],
    *,
    engine: str,
    device_count: int | None = None,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """把旧版前端模板的 params 适配成新版 custom params(在 resolve_custom_config 内调用)。

    产出**等价于用户直接传的新版参数**:下游(canonical/黑名单/merge/派生层)把它当用户直接传
    的参数处理,不感知旧模板。仅对旧模板已知键处理;其余键(用户添加)一律透传。

    - tensor-parallel-size 未填且 device_count 有值 → 补 ``=device_count``;已填以用户为准。
    - 长度键:权威长度键优先(已填透传、丢弃 length 源;未填用 input+output 生成,缺失侧记 0;
      input/output 都未填 → 跳过)。input/output-length 执行后不残留。
    - 其余旧模板已知键按引擎:原生→透传,映射→改名,非原生→丢弃(记 audit)。

    Args:
        params: 已 _to_snake 归一、尚未 canonical/黑名单处理的 config-file params。
        engine: 引擎名(vllm/vllm-ascend/sglang;其余引擎不干预,原样透传)。
        device_count: 下发卡数;用于 tensor-parallel-size 未填时默认补(= device_count)。

    Returns:
        ``(adapted, dropped)``:
            adapted: 产出的新版权威键集合(含用户添加的透传键),可继续走 canonical/黑名单。
            dropped: 被丢弃的旧模板键审计条目([{key, value, reason}, ...])。
    """
    source = dict(params)

    # 非 vllm/vllm-ascend/sglang(如 mindie / 未知引擎):旧模板仅面向 vllm/sglang,
    # 其余引擎不干预,原样透传。
    if engine not in _ENGINES:
        return source, []

    adapted: Dict[str, Any] = {}
    dropped: List[Dict[str, Any]] = []

    # 1. 长度键:权威长度键优先(透传/生成/跳过)。
    _merge_length(source, adapted, dropped, engine=engine)

    # 2. tensor-parallel-size 未填 → 默认补 = device_count(用户已填以用户为准)。
    if "tensor_parallel_size" not in source and device_count is not None:
        adapted["tensor_parallel_size"] = device_count

    # 3. 其余键:旧模板已知键按引擎映射/透传/丢弃;用户添加键一律透传。
    for key, value in source.items():
        # 长度源(input/output-length)已由 step 1 消费/丢弃,不在此重复透传。
        if key in _LEGACY_LEN_KEYS:
            continue

        if key not in _LEGACY_KEYS:
            # ── 用户基于模板添加的参数:一律透传(不映射不丢弃) ──
            adapted[key] = value
            continue

        # ── 旧模板已知键:按引擎处理 ──
        if engine in ("sglang",):
            renamed = _SGLANG_RENAME.get(key)
            if renamed is not None:
                adapted[renamed] = value  # 映射 → 等价于用户传权威键
                continue
            if key in _SGLANG_TRANSPARENT:
                adapted[key] = value  # 透传
                continue
            # sglang 非原生 → 丢弃。
            dropped.append({
                "key": key, "value": value,
                "reason": "legacy_json_adapter=非 sglang 原生参数,丢弃",
            })
        else:  # vllm / vllm-ascend
            if key in _VLLM_TRANSPARENT:
                adapted[key] = value  # 透传
            else:
                # vllm 非原生(如 enable_auto_think_choice)→ 丢弃。
                dropped.append({
                    "key": key, "value": value,
                    "reason": "legacy_json_adapter=非 vllm 原生参数,丢弃",
                })

    return adapted, dropped
