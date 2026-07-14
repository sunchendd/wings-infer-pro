"""wings_ctl — trace-first 配置解析器。"""

from __future__ import annotations

try:
    from importlib.metadata import version as _meta_version
    __version__ = _meta_version("wings-ctl")
except Exception:
    __version__ = "0.1.0.dev0"
