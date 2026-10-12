# G.FMT.07 导入部分(imports)应该按照标准库、第三方库、应用程序自定义模块的顺序排列导入

- **规则ID**：2ab10ab3-a620-4335-9fd1-8649900ae2e2
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

导入部分(imports)应按照标准库，第三方库，应用程序自定义模块的顺序排列导入，否则会影响代码结构。

**【正确示例】**

```
##### 场景1：导入顺序错误
- 修复示例1：按照标准库，第三方库，应用程序自定义模块的顺序导入
```python
import os   # 符合，标准模块放在前面
import sys  # 符合，标准模块放在前面

from oslo_config import cfg
from oslo_log import log as logging

from cinder import context
from cinder import db
```
- 修复示例2：`__future__`模块放在导入语句最前面
```python
from __future__ import print_function   # __future__模块放在导入语句最前面

import os
import sys
from time import sleep
```


```
**【错误示例】**

```
##### 场景1：导入顺序错误
- 错误示例：标准库导入在应用程序自定义模块导入之后
```python
from oslo_config import cfg
from oslo_log import log as logging

from cinder import context
from cinder import db

import os    # 不符合，标准模块应放在最前面
import sys   # 不符合，标准模块应放在最前面
```


```
**【修复建议】**

导入部分应该按照如下分组顺序导入，每个分组之间应该留一个空行：

1. 标准库

2. 第三方库

3. 应用程序自定义模块

4. 如果文件中包含`__future__`模块的导入，那么该语句应该被放在所有导入的最前面
