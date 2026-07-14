"""跨模块共享常量(仅放真正被多个模块引用的常量,勿变成大杂烩)。

当前只有一个:backend/engine 默认监听端口。由 :mod:`config_resolver`(builtin 兜底)
与 :mod:`port_plan`(ENGINE_PORT 缺省)共用,单点定义避免双写漂移。

本模块是无依赖的叶子(只含字面量),供任意层向下 import,不会引入循环。
"""

from __future__ import annotations

# backend/engine 监听端口缺省值(engine 容器内部服务地址,可由 ENGINE_PORT 覆盖)。
# proxy 对外端口(18000)、health 探针端口(19000)不属跨模块常量,不在此。
DEFAULT_ENGINE_PORT = 17000
