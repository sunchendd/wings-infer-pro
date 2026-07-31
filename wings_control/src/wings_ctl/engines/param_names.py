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


def key_to_flag(key: str) -> str:
    """engine_config key → CLI flag。

    顶层参数加 ``--`` 前缀并把下划线转连字符;点号后的嵌套配置路径原样保留。

    Args:
        key: 下划线形式的顶层参数名,或带点号的嵌套配置 key,如
            ``max_model_len`` / ``kernel_config.enable_flashinfer_autotune``。

    Returns:
        CLI flag,如 ``--max-model-len``;``kernel_config.enable_flashinfer_autotune``
        → ``--kernel-config.enable_flashinfer_autotune``。
    """
    top_level, dot, nested_path = key.partition(".")
    return f"--{top_level.replace('_', '-')}{dot}{nested_path}"


def flag_to_key(flag: str) -> str:
    """CLI flag → engine_config key。

    去掉 ``--`` 前缀(若有),把顶层参数的连字符转下划线;点号后的嵌套配置路径原样保留。

    Args:
        flag: CLI flag,如 ``--max-model-len`` 或
            ``--kernel-config.enable_flashinfer_autotune``;无 ``--`` 前缀时按主体处理。

    Returns:
        engine_config key,如 ``max_model_len`` 或
        ``kernel_config.enable_flashinfer_autotune``。
    """
    body = flag[2:] if flag.startswith("--") else flag
    top_level, dot, nested_path = body.partition(".")
    return f"{top_level.replace('-', '_')}{dot}{nested_path}"
