"""serializer — 将 engine_config 的嵌套值序列化为 CLI-ready 字符串。

规则:
- dict/list 值 → json.dumps(value, separators=(',',':'), sort_keys=False)
- 只序列化 yaml 里写了的字段,绝不补默认值
- 返回紧凑 JSON,不排序 key(保持 YAML 声明顺序)
"""

from __future__ import annotations

import json
from typing import Any


def serialize_nested_value(value: Any) -> str:
    """将 dict 或 list 序列化为紧凑 JSON 字符串。

    Args:
        value: dict 或 list 类型的值。

    Returns:
        紧凑 JSON 字符串(无空格,不排序 key)。
    """
    return json.dumps(value, separators=(",", ":"), sort_keys=False, ensure_ascii=False)
