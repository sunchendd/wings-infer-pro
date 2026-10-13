"""profile_registry — v2 资产 profile 索引 key 注册表与偏序裁决引擎。

对应设计 `docs/design/wings-yaml-v2.md` §7。

v2 以 **profile**（yaml 内声明的扁平 key-value 字典）作为查找 key，替代 v1 的
"目录结构 + 模型名正则"索引。本模块提供：

- :class:`ProfileKey`：单个索引 key 的声明（必填/参与偏序/值类型/match/is_subset）。
- :data:`PROFILE_KEYS`：注册表，新增 key 在此加一行。
- 声明式比较纯函数（match / is_subset），**无表达式求值、无 eval/exec**。
- 偏序裁决引擎 :func:`resolve`：最特化优先，等价/互不偏序报歧义。

红线（继承 AGENTS.md 与设计 5.2）：匹配为声明式比较，算子为封闭集合，注册表内硬编码，
不解析任意表达式。新增 key 必须通过代码显式注册。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ── 声明式算子（封闭集合，注册表内硬编码，不解析任意表达式）──────────────
# 数值/集合类 key 的 profile 值可为标量（精确）或带算子的 dict。
# 算子为封闭集合；`!=` 首版不提供（is_subset 语义不直观）。
_OPERATORS = frozenset({">=", "<=", ">", "<", "in", "=="})


class ProfileError(ValueError):
    """profile 匹配/裁决过程中的确定性错误（歧义、非法声明等）。"""


class ProfileAmbiguityError(ProfileError):
    """多个候选互不偏序或等价（重复资产）时抛出，由资产作者解决。"""


# ── 归一化辅助 ──────────────────────────────────────────────────────────────

def _norm_str(value: Any) -> str:
    """字符串归一：`_`→`-` + casefold（对齐设计 2.1 engine/model 匹配）。"""
    return str(value).replace("_", "-").casefold()


def _norm_set(values: Any) -> Set[str]:
    """把 hardware 集合值归一为 casefold 的 raw string 集合。

    支持三种 YAML 形态：
    - 列表/元组：``[a, b]``
    - 字符串：``"a"``
    - 流映射当集合用：``{a, b}``（PyYAML 解析为 ``{"a": None, "b": None}``，
      设计示例 `hardware: {b200, B200}` 即此形态；取键为成员）。
    """
    if isinstance(values, dict):
        # YAML 流映射当集合用：取键（值应为 null）。
        return {_norm_str(k) for k in values}
    if isinstance(values, (set, list, tuple)):
        return {_norm_str(v) for v in values}
    if isinstance(values, str):
        return {_norm_str(values)}
    raise ProfileError(f"hardware value must be a set/list/string, got {type(values).__name__}")


# ── 各 key 类型的 match（单请求是否命中）───────────────────────────────────

def _eq_str(declared: Any, ctx: Any) -> bool:
    """精确 str 匹配（engine/model）：`_`→`-` 归一 + casefold。"""
    return _norm_str(declared) == _norm_str(ctx)


def _prefix_cmp(declared: Any, ctx: Any) -> bool:
    """前缀匹配（version）：ctx 以 declared 为前缀（casefold，对齐 v1 目录层）。"""
    return _norm_str(ctx).startswith(_norm_str(declared))


def _set_mem(declared: Any, ctx: Any) -> bool:
    """集合成员匹配（hardware）：ctx 的 raw string ∈ 集合（casefold 精确）。"""
    return _norm_str(ctx) in _norm_set(declared)


# ── 数值范围归一（context_length 等 int key）───────────────────────────────

@dataclass(frozen=True)
class _Range:
    """数值约束的归一表示，用于 match 与 is_subset。

    Attributes:
        lower: (value, inclusive) 下界；None = 无下界。
        upper: (value, inclusive) 上界；None = 无上界。
        exact: 精确值（==）；None = 非精确。
        members: `in` 集合；None = 非集合成员。
    """

    lower: Optional[Tuple[int, bool]] = None
    upper: Optional[Tuple[int, bool]] = None
    exact: Optional[int] = None
    members: Optional[Set[int]] = None

    def contains(self, value: int) -> bool:
        """数值是否命中本约束。"""
        if self.exact is not None:
            return value == self.exact
        if self.members is not None:
            return value in self.members
        if self.lower is not None:
            lo, lo_inc = self.lower
            if value < lo or (value == lo and not lo_inc):
                return False
        if self.upper is not None:
            hi, hi_inc = self.upper
            if value > hi or (value == hi and not hi_inc):
                return False
        return True

    def is_subset_of(self, other: "_Range") -> bool:
        """本约束的匹配集合 ⊆ other 的匹配集合。

        本约束为全集（无任何约束，即未声明）时，只有 other 也是全集才 ⊆
        （全集 ⊄ 任何有约束的 other）；否则按各约束逐项判定。
        """
        # 本约束是全集（无约束）：仅当 other 也是全集时 ⊆。
        self_is_unconstrained = (
            self.exact is None
            and self.members is None
            and self.lower is None
            and self.upper is None
        )
        if self_is_unconstrained:
            return (
                other.exact is None
                and other.members is None
                and other.lower is None
                and other.upper is None
            )
        # 精确值：必须落在 other 的约束内。
        if self.exact is not None:
            return other.contains(self.exact)
        # 集合成员：每个成员都必须命中 other。
        if self.members is not None:
            return all(other.contains(v) for v in self.members)
        # 区间：other 必须是能包含本区间的区间。有限集（exact/members）无法包含
        # 无限区间；本区间无界的某一侧，other 也必须无界（否则边界外的值会逸出）。
        if other.exact is not None or other.members is not None:
            return False
        if self.lower is not None:
            lo, lo_inc = self.lower
            if not _covers_lower(other, lo, lo_inc):
                return False
        elif other.lower is not None:
            return False
        if self.upper is not None:
            hi, hi_inc = self.upper
            if not _covers_upper(other, hi, hi_inc):
                return False
        elif other.upper is not None:
            return False
        return True


def _covers_lower(other: _Range, lo: int, lo_inc: bool) -> bool:
    """other 的下界是否不高于 (lo, lo_inc)（即 other 能覆盖 [lo, ∞) 的下侧）。

    调用前提：调用方 self 是含下界的区间（射线或双侧区间）。有限集
    （exact/members）无法覆盖无限区间的下侧，返回 False。
    """
    if other.exact is not None or other.members is not None:
        return False
    if other.lower is None:
        return True  # other 无下界（-∞），能覆盖任何下界
    o_lo, o_lo_inc = other.lower
    is_narrower_lower = lo == o_lo and lo_inc and not o_lo_inc
    return not (lo < o_lo or is_narrower_lower)


def _covers_upper(other: _Range, hi: int, hi_inc: bool) -> bool:
    """other 的上界是否不低于 (hi, hi_inc)（即 other 能覆盖 (-∞, hi] 的上侧）。

    调用前提：调用方 self 是含上界的区间（射线或双侧区间）。有限集
    （exact/members）无法覆盖无限区间的上侧，返回 False。
    """
    if other.exact is not None or other.members is not None:
        return False
    if other.upper is None:
        return True  # other 无上界（+∞），能覆盖任何上界
    o_hi, o_hi_inc = other.upper
    is_narrower_upper = hi == o_hi and hi_inc and not o_hi_inc
    return not (hi > o_hi or is_narrower_upper)


def _parse_range(declared: Any) -> _Range:
    """把 context_length 的声明值（标量或算子 dict）归一为 :class:`_Range`。

    ``None``（未声明）→ 全集（无约束，最泛化），用于偏序比较。
    """
    if declared is None:
        return _Range()
    if isinstance(declared, dict):
        if len(declared) != 1:
            raise ProfileError(f"numeric key operator dict must declare exactly one operator, got {sorted(declared)}")
        op, raw = next(iter(declared.items()))
        if op not in _OPERATORS:
            raise ProfileError(f"unregistered operator {op!r}; available operators: {sorted(_OPERATORS)}")
        if op == "in":
            if not isinstance(raw, (list, tuple, set)):
                raise ProfileError(f"the 'in' operator requires a set/list, got {type(raw).__name__}")
            return _Range(members={int(v) for v in raw})
        value = int(raw)
        if op == "==":
            return _Range(exact=value)
        if op == ">=":
            return _Range(lower=(value, True))
        if op == ">":
            return _Range(lower=(value, False))
        if op == "<=":
            return _Range(upper=(value, True))
        if op == "<":
            return _Range(upper=(value, False))
        raise ProfileError(f"unsupported operator {op!r}")
    # 标量 → 精确
    return _Range(exact=int(declared))


def _num_cmp(declared: Any, ctx: Any) -> bool:
    """数值比较（context_length）：声明值命中 ctx 数值。"""
    try:
        ctx_value = int(ctx)
    except (TypeError, ValueError):
        return False
    return _parse_range(declared).contains(ctx_value)


def _range_subset(declared_a: Any, declared_b: Any) -> bool:
    """区间包含（context_length 偏序）：A 的匹配集合 ⊆ B 的匹配集合。"""
    return _parse_range(declared_a).is_subset_of(_parse_range(declared_b))


# ── 集合偏序（hardware）────────────────────────────────────────────────────

def _set_subset(declared_a: Any, declared_b: Any) -> bool:
    """集合包含（hardware 偏序）：A ⊆ B。"""
    return _norm_set(declared_a) <= _norm_set(declared_b)


# ── 注册表 ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProfileKey:
    """单个 profile 索引 key 的声明。

    Attributes:
        name: key 名（yaml profile 块内的键）。
        required: 必填四要素之一；缺失 → 资产无效/跳过。
        partial_order: 是否参与偏序判断（仅 True 的 key 参与 is_subset 比较）。
        value_type: 值类型（str / int / set）。
        match: (declared, ctx) -> bool 单请求命中。
        is_subset: (declared_a, declared_b) -> bool 匹配集合包含（偏序核心）。
    """

    name: str
    required: bool = False
    partial_order: bool = False
    value_type: type = str
    match: Callable[[Any, Any], bool] = None  # type: ignore[assignment]
    is_subset: Optional[Callable[[Any, Any], bool]] = None


PROFILE_KEYS: Dict[str, ProfileKey] = {
    "engine": ProfileKey("engine", required=True, value_type=str, match=_eq_str),
    "model": ProfileKey("model", required=True, value_type=str, match=_eq_str),
    "version": ProfileKey("version", required=True, value_type=str, match=_prefix_cmp),
    "hardware": ProfileKey(
        "hardware",
        required=True,
        partial_order=True,
        value_type=set,
        match=_set_mem,
        is_subset=_set_subset,
    ),
    "context_length": ProfileKey(
        "context_length",
        required=False,
        partial_order=True,
        value_type=int,
        match=_num_cmp,
        is_subset=_range_subset,
    ),
}

# 必填四要素（缺任一 → 资产无效/跳过，v1 宽容策略）。
REQUIRED_KEYS: Tuple[str, ...] = tuple(k for k, v in PROFILE_KEYS.items() if v.required)


def registered_key(name: str) -> bool:
    """key 是否已注册。"""
    return name in PROFILE_KEYS


# ── 匹配与裁决 ─────────────────────────────────────────────────────────────

def evaluate_profile(profile: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    """逐 key 用 ctx 求值，所有 key 命中才返回 True。

    规则（设计 3.1）：
    - 必填 key 必须全部命中；缺失 → 跳过 + 记录（v1 宽容策略）。
    - 可选 key 未命中（含 ctx 缺值）→ 拒绝该 yaml。
    - 未注册 key → 拒绝（离线校验脚本报错，运行时宽容跳过）。

    Args:
        profile: yaml 的 profile 块（扁平 key-value）。
        ctx: 查找上下文（engine/version/hardware/model + 可选 key）。

    Returns:
        所有 key 命中 → True；任一未命中/缺失/未注册 → False。
    """
    for key, declared in profile.items():
        spec = PROFILE_KEYS.get(key)
        if spec is None:
            # 未注册 key：运行时宽容跳过（离线校验脚本报错）。
            return False
        if key not in ctx:
            # ctx 缺值 → 拒绝（可选 key 未命中即拒绝）。
            return False
        try:
            matched = spec.match(declared, ctx[key])
        except ProfileError:
            # 非法 profile 值（离线校验脚本应已发现）：运行时宽容跳过该资产，
            # 不中断匹配（registry.md §5「匹配期间不允许报错」）。
            return False
        if not matched:
            return False
    # 必填四要素必须全部声明（缺失 → 资产无效）。
    for key in REQUIRED_KEYS:
        if key not in profile:
            return False
    return True


def is_more_specific(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """A 比 B 更特化 ⟺ A 的匹配集合 ⊆ B 的匹配集合（仅对 partial_order=True 的 key）。

    逐 key 组合偏序（设计 3.2）：A 比 B 更特化，当且仅当 A 的每个参与偏序的 key
    的匹配集合都 ⊆ B 的对应 key，且至少一个严格包含。

    Args:
        a: 候选 A 的 profile。
        b: 候选 B 的 profile。

    Returns:
        A 严格比 B 更特化 → True；否则 False。
    """
    strict = False
    for key, spec in PROFILE_KEYS.items():
        if not spec.partial_order or spec.is_subset is None:
            continue
        a_val = a.get(key)
        b_val = b.get(key)
        if a_val is None and b_val is None:
            # 双方都未声明该 key：都无约束（全集），等价，不贡献 strict。
            continue
        # 未声明的一方视为全集（最泛化），参与偏序比较。
        # 这样"不写 context_length"的资产天然比"写了 context_length"的更泛化，
        # 而非互不偏序（registry.md §3.2 语义修正）。
        if not spec.is_subset(a_val, b_val):
            return False
        if not spec.is_subset(b_val, a_val):
            strict = True
    return strict


def resolve(profiles: List[Dict[str, Any]], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """偏序裁决：从候选 profile 中选最特化者。

    流程（设计 3.2）：
    1. 过滤：match 全命中（:func:`evaluate_profile`）。
    2. 偏序：对候选两两比较 is_more_specific。
    3. 结果：唯一最特化 → 选中；多个等价（重复资产）→ 报歧义；
       多个互不偏序 → 报歧义。

    Args:
        profiles: 候选 profile 列表（每个是 yaml 的 profile 块）。
        ctx: 查找上下文。

    Returns:
        选中的最特化 profile。

    Raises:
        ProfileAmbiguityError: 无候选 / 多个等价 / 多个互不偏序。
    """
    matched = [p for p in profiles if evaluate_profile(p, ctx)]
    if not matched:
        raise ProfileAmbiguityError("no profile matched the given context")

    # 淘汰被更特化者覆盖的候选。
    winners: List[Dict[str, Any]] = []
    for candidate in matched:
        dominated = False
        for other in matched:
            if other is candidate:
                continue
            if is_more_specific(other, candidate):
                dominated = True
                break
        if not dominated:
            winners.append(candidate)

    if len(winners) == 1:
        return winners[0]

    # 多个等价（匹配集合相同）或互不偏序 → 报歧义。
    raise ProfileAmbiguityError(
        f"ambiguous profile resolution: {len(winners)} candidates are equally specific "
        f"(duplicate assets or incomparable profiles): {[sorted(w) for w in winners]}"
    )
