# -*- coding: utf-8 -*-
"""日志分析器插件模块。

该模块包含针对不同引擎、部署模式和硬件平台的日志分析插件。
"""

__all__ = [
    "VLLMSingleGPUPlugin",
    "VLLMAscendSinglePlugin",
    "SGLangSingleGPUPlugin",
    "MindIEDistributedPlugin",
    "MindIESinglePlugin",
]

from .vllm_single import VLLMSingleGPUPlugin
from .vllm_ascend_single import VLLMAscendSinglePlugin
from .sglang_single import SGLangSingleGPUPlugin
from .mindie_distributed import MindIEDistributedPlugin
from .mindie_single import MindIESinglePlugin
