# G.FMT.05 导入部分(imports)应该置于模块注释和文档字符串之后，模块全局变量和常量声明之前

- **规则ID**：94a26006-5e79-4732-886c-36153ad09876
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

导入部分(imports)应位于文件的顶端，通常是置于模块注释和文档字符串之后，模块全局变量和常量声明之前。

**【正确示例】**

```
# 【正例1】
"""This is a module

Functions of this module
"""

# 导入部分位于文档字符串之后，全局变量之前
import os
import sys

sample_global_variable = 0
M_SAMPLE_GLOBAL_CONSTANT = 0

# 【正例2】如果文件中定义了类似__all__、__version__这种全局变量（以两个下划线开头、以两个下划线结尾），那么导入部分应该放在这类定义的后面，但__future__模块的导入例外，__future__模块的导入必须放在文档字符串之后，其他内容之前。
"""This is a module

Functions of this module
"""

from __future__ import print_function

__all__ = ['hello', 'world']
__version__ = 'V1.0'

import os
import sys
from time import sleep

```
**【错误示例】**

```
##### 场景1：导入语句的位置错误
- 错误示例：导入部分位于文档字符串和全局变量之后
```python
"""This is a module
Functions of this module
""" 
sample_global_variable = 0
M_SAMPLE_GLOBAL_CONSTANT = 0
import os   # 不符合，导入位置错误
import sys   # 不符合，导入位置错误
```

```
**【修复建议】**

1. 导入语句应该置于模块注释和文档字符串之后，模块全局变量和常量声明之前。

2. 非导入语句如全局变量等应置于导入语句之后，更改环境路径为目的的代码如sys.path.append以及猴子补丁等可以视作导入代码。

3. 如果文件中定义了类似`__all__`、`__version__`这种全局变量（以两个下划线开头、以两个下划线结尾），那么导入部分应该放在这类定义的后面，但`__future__`模块的导入例外，`__future__`模块的导入必须放在文档字符串之后，其他内容之前。

故放置顺序为：

     - `__future__`模块

     - `__all__`、`__version__`这种全局变量

     - 导入模块语句
