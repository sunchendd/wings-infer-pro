# G.IMP.02 使用 from ... import ... 语句的注意事项

- **规则ID**：0d3ee8ca-d24c-4187-814d-bc1db426df71
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

import和from ... import ...作为Python最常用的两种导入方式，各有优缺点，要结合实际场景进行选取。



导入方式 import module from module import ...

主要优点 使用时，模块-对象对应关系明确 严格控制使用的对象清单

主要缺点 module.obj的使用方式冗余啰嗦 模块间存在同名对象时需要通过from ... import ... as ...重命名，使用时容易混淆

如果模块名较长，为了减少使用时的语句冗余，可以使用import module as mo的方式，也可以使用from module import ...的方式。



禁止使用from ... import *，该方法会导入模块内所有非_前缀的对象，存在以下缺点：



1.如果多个模块存在同名对象，后导入的对象会覆盖先导入的同名对象，开发者无法快速识别该覆盖行为；

2.无法明确各对象的所属模块，给代码的功能调测、长期维护等带来额外的开销。

测试代码使用from ... import *，同样存在上述缺点。虽然测试代码不会在生产环境运行，但会给开发调试带来不必要的麻烦，建议避免使用该方式导入。

**【正确示例】**

```
# 【正例1】常见的导入方式，两种导入方式按需混用。
import os
import sys

from sqlalchemy import create_engine

# 【正例2】对于某些导入耗时较高的模块，可以使用示例方式控制使用的对象清单，同时规避易混淆的缺点。
from os import path as os_path
from sys import path as sys_path

```
**【错误示例】**

```
from sys import *  # 不符合，os模块的path被sys模块的path覆盖

```
**【修复建议】**

使用 from ... import ... 语句参照编程规范的注意事项
