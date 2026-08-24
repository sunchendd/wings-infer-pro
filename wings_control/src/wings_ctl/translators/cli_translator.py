"""CLI translator for user-named parameters."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from wings_ctl.translators.param_mapping import (
    MAAS_CONTRACT_ALLOWLIST,
    drop_reason,
    translate,
)

logger = logging.getLogger(__name__)


def filter_maas_contract_overrides(
    raw_user_cli_overrides: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """按 MaaS 契约白名单过滤 canonical key 覆盖层。

    Args:
        raw_user_cli_overrides: canonical engine_config key 形态的 user_cli 覆盖层。

    Returns:
        二元组 ``(allowed, dropped)``:
        - ``allowed``: 在 MaaS 契约白名单内,可进入最终 user_cli merge。
        - ``dropped``: 不在白名单,记录审计行(``key/value/reason``)。

    维护者说明(防止误判为 allowlist 漏项):
        CLI 语法能解析某个 ``--flag``,**不代表**它属于当前 MaaS 对外契约。
        ``cli._build_parser`` 注册 + ``cli._collect_user_cli_overrides`` 收集只说明
        "程序认识该参数、已收进 raw override dict";真正决定"能否进 user_cli merge"的是
        ``MAAS_CONTRACT_ALLOWLIST``。不在该白名单的 key(当前如 ``quantization`` /
        ``enable_prefix_caching`` / ``enable_expert_parallel``)会在进入 merge **之前**被
        warn-only dropped:打 WARNING + 记 dropped reason
        (``maas_status=not_in_maas_contract_allowlist``)进 audit,
        **不进 final engine_config / argv、不阻塞启动**。
        这是**当前契约策略(非契约参数优雅降级)**,不是解析遗漏、也不是 allowlist 漏项——
        要对外承诺某参数时,才把它补进 ``MAAS_CONTRACT_ALLOWLIST``(属扩契约,需同步测试)。
    """
    allowed: Dict[str, Any] = {}
    dropped: List[Dict[str, Any]] = []
    for key, value in raw_user_cli_overrides.items():
        if key in MAAS_CONTRACT_ALLOWLIST:
            allowed[key] = value
            continue
        reason = "maas_status=not_in_maas_contract_allowlist"
        logger.warning(
            "Parameter '%s' is not in the MaaS contract allowlist; dropping it in warn-only mode",
            key,
        )
        dropped.append({"key": key, "value": value, "reason": reason})
    return allowed, dropped


class CLITranslator:
    """Translate user CLI overrides into engine-native keys."""

    @staticmethod
    def translate_overrides(
        overrides: Dict[str, Any],
        engine: str,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Return translated dict and dropped key-value entries for audit."""
        maas_allowed, maas_dropped = filter_maas_contract_overrides(overrides)
        translated: Dict[str, Any] = {}
        dropped: List[Dict[str, Any]] = list(maas_dropped)

        for key, value in maas_allowed.items():
            mapped_key = translate(key, engine)
            if mapped_key is None:
                reason = drop_reason(key, engine) or "maas_status=丢弃"
                if key == "enable_auto_think_choice":
                    logger.warning(
                        "enable_auto_think_choice is not passed through as a user_cli parameter; "
                        "FeatureOverlay reasoning gate handles it. Whether reasoning parameters such as "
                        "--reasoning-parser are rendered depends on model.yaml features.reasoning.args."
                    )
                dropped.append({"key": key, "value": value, "reason": reason})
                continue
            translated[mapped_key] = value

        return translated, dropped
