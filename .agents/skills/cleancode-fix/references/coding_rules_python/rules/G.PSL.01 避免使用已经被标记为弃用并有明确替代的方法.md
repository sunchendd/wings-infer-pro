# G.PSL.01 避免使用已经被标记为弃用并有明确替代的方法

- **规则ID**：cc162847-2a8d-4664-a7a8-4333d60dbfa2
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

当代码运行出现DeprecationWarning，明确指出某些模块、类或函数计划废弃，并给出了新的替代方案时，必须按照其提示的方法、版本正确地使用新方案替代计划废弃的老方案。

**【正确示例】**

```
# 【正例1】
from collections.abc import Iterable

```
**【错误示例】**

```
# 【反例1】
from collections import Iterable  # DeprecationWarning: Using or importing the ABCs from 'collections' instead of from 'collections.abc' is deprecated, and in 3.8 it will stop working

```
**【修复建议】**

使用新版本的函数替换旧版本的函数
