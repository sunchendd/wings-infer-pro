"""engine/native flag ↔ engine_config key 名称转换(单点约定)。

约定:engine_config 用下划线 key(如 ``max_model_len``);渲成 CLI flag 时前缀 ``--``
且下划线转连字符(``--max-model-len``)。**只在下划线↔连字符间转换,不触碰点号**——
如 ``attention_config.use_fp4_indexer_cache`` 的点号原样保留。

此前该约定在 ``vllm_adapter.render_param_tokens``(key→flag)与
``strategy/feature_overlay.parse_feature_args``(flag→key)两处各写一份 ``.replace``,
收口到本模块避免两处漂移。纯字符串函数、无依赖,可被任意层向下 import。
"""

from __future__ import annotations


def key_to_flag(key: str) -> str:
    """engine_config key → CLI flag。

    前缀 ``--`` 并把下划线转连字符;**点号不动**。

    Args:
        key: 下划线形式的参数名,如 ``max_model_len``。

    Returns:
        CLI flag,如 ``--max-model-len``;``attention_config.use_fp4_indexer_cache``
        → ``--attention-config.use-fp4-indexer-cache``(点号保留)。
    """
    return f"--{key.replace('_', '-')}"


def flag_to_key(flag: str) -> str:
    """CLI flag → engine_config key。

    去掉 ``--`` 前缀(若有)并把连字符转下划线;**点号不动**。

    Args:
        flag: CLI flag,如 ``--max-model-len``;无 ``--`` 前缀时按主体原样处理。

    Returns:
        下划线形式的 key,如 ``max_model_len``。
    """
    body = flag[2:] if flag.startswith("--") else flag
    return body.replace("-", "_")
