"""Topology 枚举 — 部署拓扑类型。

当前支持 STANDALONE 和 MULTI_NODE。PD 相关枚举保留给后续能力。
"""

from enum import Enum


class Topology(Enum):
    STANDALONE = "standalone"
    MULTI_NODE = "multi_node"
    PD_PREFILL = "pd_prefill"
    PD_DECODE = "pd_decode"
