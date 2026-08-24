"""从模型目录读权重体积 + 结构参数(显存闸 weight_bytes / 收缩守卫 num_attention_heads)。

- ``resolve_weight_bytes``:首选 ``model.safetensors.index.json`` 的 ``metadata.total_size``
  (精确、无需遍历),兜底 ``sum(*.safetensors)``;皆无 → raise。
- ``read_num_attention_heads``:读 ``config.json`` 的 ``num_attention_heads``;读不到返回 None
  (调用方按 warn-skip 放行,守卫尽力而为、非可运行性证明)。

生产 resolve 时 ``--model-path`` 已挂载可读;测试注入 stub 不碰真权重(不在生产入口塞 test-bypass)。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def resolve_weight_bytes(model_path: str) -> int:
    """读模型权重总字节数(显存闸 weight_bytes)。

    Args:
        model_path: 模型目录(``--model-path``,生产已挂载可读)。

    Returns:
        权重总字节数(该精度量化后落盘大小,正合"要装进显存"的量纲)。

    Raises:
        ValueError: 目录不存在,或既无 ``model.safetensors.index.json`` 也无 ``*.safetensors``
            (无法判定体积;显存闸缺输入,直接失败)。
    """
    root = Path(model_path)
    if not root.is_dir():
        raise ValueError(f"model-path is not a readable directory: {model_path!r}; weight size is required")

    # 首选:safetensors index 的 metadata.total_size(精确)
    index = root / "model.safetensors.index.json"
    if index.is_file():
        try:
            meta = json.loads(index.read_text(encoding="utf-8")).get("metadata") or {}
            total = meta.get("total_size")
            if isinstance(total, int) and total > 0:
                logger.debug("weight_bytes read from index.json total_size=%d", total)
                return total
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s (%s); falling back to *.safetensors enumeration", index, exc)

    # 兜底:遍历 *.safetensors 累加字节
    shards = sorted(root.glob("*.safetensors"))
    if shards:
        total = sum(p.stat().st_size for p in shards)
        logger.debug("weight_bytes summed from %d *.safetensors files: %d", len(shards), total)
        return total

    raise ValueError(
        f"Cannot determine weight size: {model_path!r} contains neither model.safetensors.index.json nor *.safetensors"
    )


def read_num_attention_heads(model_path: str) -> Optional[int]:
    """读 ``config.json`` 的 ``num_attention_heads``(TP 收缩守卫用)。

    Args:
        model_path: 模型目录。

    Returns:
        ``num_attention_heads`` 整数;读不到(无 config.json / 无该字段 / 解析失败)返回 None,
        调用方据此 warn-skip 放行(守卫尽力而为)。
    """
    cfg = Path(model_path) / "config.json"
    if not cfg.is_file():
        return None
    try:
        heads = json.loads(cfg.read_text(encoding="utf-8")).get("num_attention_heads")
        return heads if isinstance(heads, int) and heads > 0 else None
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s (%s); skipping the attention-head divisibility guard", cfg, exc)
        return None
