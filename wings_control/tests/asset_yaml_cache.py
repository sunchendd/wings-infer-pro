"""资产 YAML 读取缓存(测试专用)。

为什么需要:``config/engines`` 与 ``src/wings_accel/smart-accel`` 共 5000+ 个 YAML(约 43MB),
多个不变量测试各自整树解析同一批文件。纯 Python ``yaml.safe_load`` 全量单次约 26s,而同一批
文件在同一进程里被重复解析 4~6 次,是测试耗时的主要来源(单文件约 5~8ms)。

安全约束:只走 safe 构造器(``SafeLoader``,或 C 实现的 ``CSafeLoader``)。二者都不注册
``!!python/object``、``!!python/object/apply`` 等标签的构造函数,危险载荷抛
``ConstructorError``,无法构造任意 Python 对象。代码中不调用 yaml 模块的 load 系列入口
(含其 unsafe 变体):静态检视规则把裸 load 视为高风险,而这里只需要"用安全构造器解析单个
文档"这一能力,故直接驱动 loader 类(与该库 load 入口的内部实现一致,并显式 dispose)。

缓存键为 ``(路径, mtime_ns, size)``:文件未变时复用解析结果,文件被改写或替换后自动失效,
解析异常不入缓存,因此不改变任何测试的可见行为。解析优先使用 ``CSafeLoader``——它在当前
全部 5226 个资产上与纯 Python ``SafeLoader`` 逐文件结果一致,速度快约 9 倍;C 扩展不可用时
回退到 ``SafeLoader``。

``load_asset_yaml`` 每次返回解析结果的**深拷贝**:调用方可以自由修改返回值,不会影响缓存,
也不会把状态泄漏给同一进程里后续的测试。因此它对外等价于 ``yaml.safe_load(路径文本)``,
只是把昂贵的解析换成了便宜的拷贝(实测拷贝约为解析耗时的 7%)。测试之间唯一残留的耦合是
"第一个读某文件的测试承担解析开销",不影响任何断言结果。
"""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# 只允许 safe 构造器:C 实现 CSafeLoader 优先,不可用时回退纯 Python SafeLoader。
_LOADER = getattr(yaml, "CSafeLoader", None) or yaml.SafeLoader


def _parse(text: str) -> Any:
    """用 safe 构造器解析单个 YAML 文档;``!!python/*`` 等危险标签抛 ``ConstructorError``。"""
    loader = _LOADER(text)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


@lru_cache(maxsize=None)
def _parse_cached(path: str, mtime_ns: int, size: int) -> Any:
    """解析 YAML 并缓存。``mtime_ns`` 与 ``size`` 只作为缓存键,不参与解析。"""
    return _parse(Path(path).read_text(encoding="utf-8"))


def load_asset_yaml(path: Path) -> Any:
    """读取资产 YAML。内容未变时复用解析结果,并返回独立副本;空文件返回 ``None``。"""
    stat = path.stat()
    return copy.deepcopy(_parse_cached(str(path), stat.st_mtime_ns, stat.st_size))
