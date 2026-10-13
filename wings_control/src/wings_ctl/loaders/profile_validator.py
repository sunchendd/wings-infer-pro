"""profile_validator — v2 资产合法性离线校验。

对应设计 `docs/design/wings-yaml-v2.md` §8。

匹配期间不允许报错（资产合法性错误不中断运行时匹配）。资产合法性由**离线校验脚本**
在代码开发阶段检查，匹配期间一律宽容（跳过 + 记录，0 命中时随报错信息暴露）。

检查项：
- 必填四要素缺失
- 未注册 key
- 必填 key 值非法
- 可选 key 多值/多算子叠加
- `hardware` 值 ∉ 合法硬件表

本模块为纯函数，不依赖 fcntl，可独立 dry-run 验证。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from wings_ctl.loaders.profile_registry import (
    PROFILE_KEYS,
    REQUIRED_KEYS,
    _OPERATORS,
    _norm_set,
    _norm_str,
    _parse_range,
)


@dataclass
class ValidationIssue:
    """单条资产校验问题。

    Attributes:
        path: 资产文件路径（或 "<inline>"）。
        message: 可定位的错误描述。
        severity: "error"（阻断）或 "warning"（提示）。
    """

    path: str
    message: str
    severity: str = "error"


@dataclass
class ValidationResult:
    """资产校验汇总。

    Attributes:
        issues: 全部校验问题。
        valid: 是否无 error 级问题。
    """

    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]


@dataclass
class _KeyValidationContext:
    """单个 key 值校验的共享上下文。

    Attributes:
        result: 校验结果累加器。
        path: 资产文件路径（用于可定位错误信息）。
        legal_hardware: 合法硬件表（casefold 集合）；None = 不校验 hardware 合法性。
    """

    result: ValidationResult
    path: str
    legal_hardware: Optional[Set[str]]


def validate_profile(
    profile: Dict[str, Any],
    *,
    path: str = "<inline>",
    legal_hardware: Optional[Set[str]] = None,
) -> ValidationResult:
    """校验单个 profile 块的资产合法性。

    Args:
        profile: yaml 的 profile 块（扁平 key-value）。
        path: 资产文件路径（用于可定位错误信息）。
        legal_hardware: 合法硬件表（casefold 集合）；None = 不校验 hardware 合法性。

    Returns:
        :class:`ValidationResult`，含全部校验问题。
    """
    result = ValidationResult()
    if not isinstance(profile, dict):
        result.issues.append(ValidationIssue(path, "profile 块必须是 dict"))
        return result

    # 1. 必填四要素缺失
    for key in REQUIRED_KEYS:
        if key not in profile:
            result.issues.append(ValidationIssue(path, f"必填四要素缺失：{key}"))

    # 2. 未注册 key
    for key in profile:
        if key not in PROFILE_KEYS:
            result.issues.append(
                ValidationIssue(path, f"未注册 profile key：{key!r}（请在 PROFILE_KEYS 注册）")
            )

    # 3. 逐 key 值合法性
    ctx = _KeyValidationContext(result, path, legal_hardware)
    for key, declared in profile.items():
        spec = PROFILE_KEYS.get(key)
        if spec is None:
            continue  # 未注册 key 已在上面报错
        _validate_key_value(ctx, key, spec, declared)

    return result


def _validate_key_value(
    ctx: _KeyValidationContext,
    key: str,
    spec,
    declared: Any,
) -> None:
    """校验单个 key 的值合法性。"""
    # 多算子叠加：仅数值（int）key 的算子 dict 只能有一个算子。
    # set 类型 key（hardware）的 dict 值是 YAML 流映射当集合用（{a, b} → {"a": None, "b": None}），
    # 取键为成员，不按算子 dict 解释。
    if isinstance(declared, dict) and spec.value_type is int:
        if len(declared) != 1:
            ctx.result.issues.append(
                ValidationIssue(ctx.path, f"key {key!r} 的算子 dict 只能有一个算子，得到 {sorted(declared)}")
            )
            return
        op = next(iter(declared))
        if op not in _OPERATORS:
            ctx.result.issues.append(
                ValidationIssue(ctx.path, f"key {key!r} 使用未注册算子 {op!r}；可用：{sorted(_OPERATORS)}")
            )
            return

    # 值类型校验
    if spec.value_type is int:
        try:
            _parse_range(declared)
        except (TypeError, ValueError) as exc:
            ctx.result.issues.append(ValidationIssue(ctx.path, f"key {key!r} 值非法：{exc}"))
    elif spec.value_type is set:
        try:
            values = _norm_set(declared)
        except Exception as exc:  # noqa: BLE001
            ctx.result.issues.append(ValidationIssue(ctx.path, f"key {key!r} 值非法：{exc}"))
            return
        # hardware 值 ∉ 合法硬件表 → warning（不阻断）。硬件表是增量维护的登记表，
        # 不完整是预期；下发硬件不在表中不报错，只是不匹配任何 v2 YAML → 走 V1 回退。
        # 仅 hardware key 做此校验；其他 set 类型 key（如 cpu_arch）不属于硬件表范围。
        if key == "hardware" and ctx.legal_hardware is not None:
            legal_norm = {_norm_str(h) for h in ctx.legal_hardware}
            unknown = values - legal_norm
            if unknown:
                ctx.result.issues.append(
                    ValidationIssue(
                        ctx.path,
                        f"key {key!r} 含未登记硬件：{sorted(unknown)}（不在合法硬件表内，"
                        "建议在 hardware_table.yaml 补充；不影响匹配，未登记硬件不匹配任何 v2 YAML）",
                        severity="warning",
                    )
                )
    elif spec.value_type is str:
        if not isinstance(declared, str):
            ctx.result.issues.append(
                ValidationIssue(ctx.path, f"key {key!r} 值必须是字符串，得到 {type(declared).__name__}")
            )


def validate_assets(
    assets: List[Dict[str, Any]],
    *,
    legal_hardware: Optional[Set[str]] = None,
) -> ValidationResult:
    """批量校验多个资产（每个含 path + profile）。

    Args:
        assets: 资产列表，每项为 ``{"path": str, "profile": dict}``。
        legal_hardware: 合法硬件表（casefold 集合）。

    Returns:
        :class:`ValidationResult`，汇总全部问题。
    """
    result = ValidationResult()
    for asset in assets:
        path = asset.get("path", "<inline>")
        profile = asset.get("profile")
        if not isinstance(profile, dict):
            result.issues.append(ValidationIssue(path, "资产缺少 profile 块"))
            continue
        sub = validate_profile(profile, path=path, legal_hardware=legal_hardware)
        result.issues.extend(sub.issues)
    return result
