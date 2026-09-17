"""AIPerf 工具配置。

配置以 JSON 文件承载,加载顺序(后者覆盖前者):
内置默认 → ``/etc/aiperf/aiperf.json`` → ``./aiperf.json`` → ``--config`` 指定文件。
所有路径类字段集中在 ``AiperfConfig``,模块不各自硬编码,便于部署方覆盖。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from errors import ConfigError

logger = logging.getLogger("aiperf.config")

SYSTEM_CONFIG_PATH = Path("/etc/aiperf/aiperf.json")
LOCAL_CONFIG_NAME = "aiperf.json"


@dataclass(frozen=True)
class AiperfConfig:
    """AIPerf 工具配置快照(不可变;路径均为宿主机侧)。"""

    license_dir: Path = Path("/etc/aiperf/license")
    board_serial_path: Path = Path("/sys/class/dmi/id/board_serial")
    # 预留:后续子命令(部署/诊断等)的配置项挂到这里,避免多处定义。
    extra: Dict[str, Any] = field(default_factory=dict)


def _from_mapping(base: AiperfConfig, data: Dict[str, Any], source: str) -> AiperfConfig:
    """把一层 JSON dict 叠到现有配置上;未知键进 ``extra`` 不报错(向前兼容)。"""
    if not isinstance(data, dict):
        raise ConfigError(f"config root must be a JSON object: {source}")
    known = {"license_dir", "board_serial_path"}
    overrides: Dict[str, Any] = {}
    extra = dict(base.extra)
    for key, value in data.items():
        if key in known:
            if not isinstance(value, str) or not value:
                raise ConfigError(f"config field '{key}' must be a non-empty string ({source})")
            overrides[key] = Path(value)
        else:
            extra[key] = value
    return replace(base, extra=extra, **overrides)


def load_config(explicit: Optional[Path] = None) -> AiperfConfig:
    """按 默认 → 系统配置 → 本地配置 → 显式指定 顺序合成最终配置。

    显式 ``--config`` 文件不存在直接报错(用户点名要它);自动搜索路径
    缺失属正常情况,静默跳过。
    """
    config: AiperfConfig = AiperfConfig()
    search: List[tuple[Path, bool]] = [(SYSTEM_CONFIG_PATH, False), (Path(LOCAL_CONFIG_NAME), False)]
    if explicit is not None:
        search.append((explicit, True))
    for path, required in search:
        if not path.is_file():
            if required:
                raise ConfigError(f"config file not found: {path}")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"failed to load config {path}: {exc}") from exc
        config = _from_mapping(config, data, str(path))
        logger.debug("loaded config: %s", path)
    return config
