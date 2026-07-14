"""resolve_config_root — 确定配置资产根目录。

三级优先:
1. 显式参数(调用方传入)
2. 环境变量 WINGS_CTL_CONFIG_ROOT
3. 开发模式:从本文件向上找到含 pyproject.toml 的目录(项目根)下的 config/
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_ENV_KEY = "WINGS_CTL_CONFIG_ROOT"


def resolve_config_root(explicit: Optional[Path] = None) -> Path:
    """确定配置资产根目录。

    Args:
        explicit: 若提供,直接使用此路径。

    Returns:
        config 目录的 Path。

    Raises:
        FileNotFoundError: 无法定位 config 目录时。
    """
    # 1. 调用方显式传入(测试/CLI 均走这条)
    if explicit is not None:
        return Path(explicit)

    # 2. 环境变量(部署时设置)
    env_val = os.environ.get(_ENV_KEY)
    if env_val:
        return Path(env_val)

    # 3. 开发模式:从本文件向上找到含 pyproject.toml 的目录(即项目根)
    here = Path(__file__).resolve().parent
    for ancestor in [here] + list(here.parents):
        if (ancestor / "pyproject.toml").exists():
            candidate = ancestor / "config"
            if candidate.is_dir():
                return candidate
            break

    raise FileNotFoundError(
        f"Cannot locate config root. Set {_ENV_KEY} environment variable "
        "or pass an explicit path."
    )
