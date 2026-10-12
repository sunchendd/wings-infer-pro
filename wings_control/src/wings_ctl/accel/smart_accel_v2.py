"""smart_accel_v2 — v2 合一文件的加速块解析入口。

对应设计 `docs/design/wings-yaml-v2.md` §9。

v2 合一文件的 `smart_accel` 块与 V1 独立 smart-accel YAML 的 `smart_accel` 块**结构相同**
（`standalone` / `multi_node` / `pd_disaggregation` 分场景、`strategies.{name}.decoding` 等）。
因此复用 `wings_accel.yaml_loader.load_smart_accel_from_yaml` 从合一文件构造
`SmartAccelInput`，再调 `func_smart_accel` 解析——**不再走 `find_smart_accel_yaml_path`
独立扫描**。

本模块为纯逻辑，guard-import `wings_accel`（模块缺失 → 空 :class:`AccelResult` no-op）。
"""

from __future__ import annotations

import logging
import os

from wings_ctl.accel.smart_accel import AccelResult, build_load_flags, collect_accel_switches, collect_output
from wings_ctl.loaders.v2_loader import V2Asset

logger = logging.getLogger(__name__)


def _import_accel():
    """guard-import wings-accel 模块。

    Returns:
        模块对象（需含 ``load_smart_accel_from_yaml`` + ``func_smart_accel`` + ``LoadFlags``）；
        缺失/不完整 → None（accel 关闭，主流程不受影响）。
    """
    try:
        import wings_accel as mod  # 顶层包
    except Exception:  # pragma: no cover - 取决于模块是否合入
        return None
    if not all(hasattr(mod, name) for name in ("load_smart_accel_from_yaml", "func_smart_accel", "LoadFlags")):
        return None
    return mod


def apply_smart_accel_v2(
    asset: V2Asset,
    *,
    topology: str | None = None,
    tp_size: int = 0,
    dp_size: int = 0,
    gpu_count: int | None = None,
    pd_role: str | None = None,
    enabled: bool = True,
    env: dict | None = None,
) -> AccelResult:
    """从 v2 合一文件解析加速块，复用 `func_smart_accel`。

    Args:
        asset: 已匹配的 v2 合一资产（含 `smart_accel` 块）。
        topology: 部署拓扑（standalone/multi_node/pd_prefill/pd_decode）。
        tp_size: TP 大小（供 KV 内存 auto 估算 worker_count）。
        dp_size: DP 大小。
        gpu_count: 卡数。
        pd_role: PD 角色（P/D/none）。
        enabled: 是否启用加速（MaaS 门控）；False → 空 :class:`AccelResult`（no-op）。
        env: MaaS 环境变量字典；None → 用 os.environ。

    Returns:
        :class:`AccelResult`：加速产出（engine_config / env / audit / packages 等）。
        模块缺失或普通可选集成故障 → 空 :class:`AccelResult`（no-op）。
    """
    if not enabled:
        return AccelResult()
    mod = _import_accel()
    if mod is None:
        logger.warning("wings-accel module is unavailable; v2 smart_accel is no-op")
        return AccelResult()
    try:
        switches = collect_accel_switches(os.environ if env is None else env)
        if pd_role is not None:
            switches["pd_role"] = pd_role
        flags = build_load_flags(
            mod,
            switches,
            topology=topology,
            tp_size=tp_size,
            dp_size=dp_size,
            gpu_count=gpu_count,
        )
        smart_input = mod.load_smart_accel_from_yaml(str(asset.path), flags)
        if smart_input is None:
            logger.warning("v2 smart_accel: no SmartAccelInput from %s", asset.path)
            return AccelResult()
        output = mod.func_smart_accel(smart_input)
        return collect_output(output)
    except Exception as exc:  # optional integration 故障按既有契约降级；配置错误不能吞掉。
        configuration_error = getattr(mod, "SmartAccelConfigurationError", None)
        if isinstance(configuration_error, type) and isinstance(exc, configuration_error):
            raise
        logger.warning("v2 smart_accel invocation failed; continuing without acceleration: %s", exc)
        return AccelResult()
