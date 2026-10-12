# G.IMP.01 使用绝对路径导入模块

- **规则ID**：c33e59d7-d8b8-46fd-bbe3-858326f7d85a
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

使用正确的导入方式导入模块，可以保证代码可读性，否则可能会导致运行错误。

**【正确示例】**

```
##### 场景1：使用绝对和相对导入模块
- 修复示例：按正确顺序导入模块
```python
from third_lib import module_a  # 三方库使用绝对路径
from huawei_sdk import module_b  # 二方库使用绝对路径
from .module_c.module_cc import ClassD  # 本项目库可以使用相对路径
```

```
**【错误示例】**

```
##### 场景1：使用绝对和相对导入模块
- 错误示例：在同一个文件内，对`mypkg`同时使用绝对路径和相对路径导入，不利于代码维护
```python
# mypkg/mymodule.py
from . import module_a
from mypkg.module_b import SomeClass   # 不符合
```
- 错误示例：在不同文件内，对`mypkg`同时使用绝对路径和相对路径导入，不利于代码维护
```python
# mypkg/module_a.py
from mypkg.module_b import SomeClass
```
- 错误示例：同时需要具备可执行和可导入的文件内，使用相对路径导入，会发生导入错误
```python
# test_relative_import/model_convert.py
def str2int(_in):
    if not isinstance(_in, str):
        raise UserDefined.InvalidInput()
    return int(_in)
```

```
**【修复建议】**

1. 应该使用绝对路径导入（absolute imports），避免使用相对路径导入（relative imports），使用绝对路径可以清晰明确地知道所导入模块的所属包和完整路径，在出现导入错误时更容易定位，能够减少调整代码路径时的配套修改工作量。项目库内的代码，对项目库本身模块的导入，可以使用相对路径。

2. 如果代码的路径较深（例如导入代码的语句需要换行时），可以使用相对路径导入。

3. 禁止对外部库（包括系统库、三方库和二方库）使用相对路径导入。

4. 禁止对同一个包的导入，同时使用绝对路径和相对路径。
