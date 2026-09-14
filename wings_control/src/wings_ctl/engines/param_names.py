"""engine/native flag ↔ engine_config key 名称转换(单点约定)。

约定:engine_config 顶层参数用下划线 key(如 ``max_model_len``);渲成 CLI flag 时前缀
``--`` 且顶层参数的下划线转连字符(``--max-model-len``)。点号后的内容是引擎原生的
嵌套配置路径,必须原样保留——如 ``kernel_config.enable_flashinfer_autotune`` 渲成
``--kernel-config.enable_flashinfer_autotune``。

此前该约定在 ``vllm_adapter.render_param_tokens``(key→flag)与
``strategy/feature_overlay.parse_feature_args``(flag→key)两处各写一份 ``.replace``,
收口到本模块避免两处漂移。纯字符串函数、无依赖,可被任意层向下 import。
"""

from __future__ import annotations


# vLLM 的 ``cc.*`` 顶层前缀(pass 配置,如 cc.pass_config.fuse_allreduce_rms)是**单横线**
# flag(``-cc.xxx=value``),与其余顶层 ``--`` 双横线参数不同。这是引擎原生命名差异,
# 只能按顶层前缀特判,不能套用通用的 ``--`` 规则。封闭枚举,不扩散。
_SINGLE_DASH_TOP_LEVEL = frozenset({"cc"})


def key_to_flag(key: str) -> str:
    """engine_config key → CLI flag。

    顶层参数加 ``--`` 前缀并把下划线转连字符;点号后的嵌套配置路径原样保留。
    vLLM 的 ``cc.*`` 顶层前缀按引擎惯例改用单横线 ``-``。

    Args:
        key: 下划线形式的顶层参数名,或带点号的嵌套配置 key,如
            ``max_model_len`` / ``kernel_config.enable_flashinfer_autotune``。

    Returns:
        CLI flag,如 ``--max-model-len``;``kernel_config.enable_flashinfer_autotune``
        → ``--kernel-config.enable_flashinfer_autotune``;``cc.pass_config.fuse_allreduce_rms``
        → ``-cc.pass_config.fuse_allreduce_rms``。
    """
    top_level, dot, nested_path = key.partition(".")
    prefix = "-" if top_level in _SINGLE_DASH_TOP_LEVEL else "--"
    return f"{prefix}{top_level.replace('_', '-')}{dot}{nested_path}"


def flag_to_key(flag: str) -> str:
    """CLI flag → engine_config key。

    去掉 ``--`` / ``-cc`` 前缀(若有),把顶层参数的连字符转下划线;点号后的嵌套配置路径原样保留。

    Args:
        flag: CLI flag,如 ``--max-model-len`` 或
            ``--kernel-config.enable_flashinfer_autotune`` 或单横线 ``-cc.pass_config...``;
            无前缀时按主体处理。

    Returns:
        engine_config key,如 ``max_model_len`` 或
        ``kernel_config.enable_flashinfer_autotune``。
    """
    if flag.startswith("--"):
        body = flag[2:]
    elif flag.startswith("-"):
        body = flag[1:]
    else:
        body = flag
    top_level, dot, nested_path = body.partition(".")
    return f"{top_level.replace('-', '_')}{dot}{nested_path}"
