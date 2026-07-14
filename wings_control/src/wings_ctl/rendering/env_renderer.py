"""env_renderer — 安全的 env export 渲染。

⚠️ 安全敏感代码,需人工 review。

规则:
- 值不含 '$':export KEY=<shlex.quote(str(value))>  (纯字面,安全转义)
- 值含 '$':白名单校验 — 移除所有合法变量引用 $NAME / ${NAME} / ${NAME:+value} / ${NAME:-value} 后,
  若剩余串仍含 '$' 或反引号 → raise ValueError 拒绝。
  通过校验后用双引号包裹,让 shell 展开合法 $VAR。
- 双引号内转义 \\ 和 "。
"""

from __future__ import annotations

import re
import shlex
from typing import Any

# 合法变量引用:$NAME / ${NAME} / ${NAME:+value} / ${NAME:-value}
# NAME = [A-Za-z_][A-Za-z0-9_]*
# 支持 shell 参数扩展语法: ${VAR:+value} (if-set) / ${VAR:-value} (default)
_VALID_VAR_REF = re.compile(
    r'\$\{[A-Za-z_][A-Za-z0-9_]*:[+-][^}]*\}|\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*'
)


def _validate_dollar_value(value: str) -> None:
    """白名单校验:先拒命令替换,再移除合法 $VAR / ${VAR} / ${VAR:+val} / ${VAR:-val},剩余不得含 $ 或反引号。

    Raises:
        ValueError: 值含不安全的 $ 构造(命令替换 $(...) / 反引号 / 孤立 $)。
    """
    # 先拒命令替换($(...) / 反引号)——即使它藏在 ${VAR:-...} / ${VAR:+...} 默认值里。
    # 否则会被 _VALID_VAR_REF 的 [^}]* 吞掉而漏检。参数扩展本身不执行命令,因此允许。
    if "$(" in value or "`" in value:
        raise ValueError(
            f"Env value contains unsafe shell constructs "
            f"(command substitution $(...) / backtick forbidden): {value!r}"
        )

    # 移除所有合法变量引用
    residual = _VALID_VAR_REF.sub("", value)

    # 剩余串不得含 $ 或反引号
    if "$" in residual or "`" in residual:
        raise ValueError(
            f"Env value contains unsafe shell constructs "
            f"(only $NAME, ${{NAME}}, ${{NAME:+value}} and ${{NAME:-value}} variable references are allowed): {value!r}"
        )


def render_env_export(key: str, value: Any) -> str:
    """将 key=value 渲染为安全的 export 语句。

    Args:
        key: 环境变量名。
        value: 环境变量值(任意类型,str() 转换)。

    Returns:
        完整的 export 语句字符串(不含换行符)。

    Raises:
        ValueError: 值含不安全的 shell 构造。
    """
    str_value = str(value)

    if "$" not in str_value and "`" not in str_value:
        # 纯字面:shlex.quote 处理所有特殊字符
        return f"export {key}={shlex.quote(str_value)}"

    # 含 $ 或 ` → 白名单校验
    _validate_dollar_value(str_value)

    # 通过校验:用双引号包裹,让 shell 展开合法 $VAR
    # 转义双引号和反斜杠(双引号内的特殊字符)
    escaped = str_value.replace("\\", "\\\\").replace('"', '\\"')
    return f'export {key}="{escaped}"'
