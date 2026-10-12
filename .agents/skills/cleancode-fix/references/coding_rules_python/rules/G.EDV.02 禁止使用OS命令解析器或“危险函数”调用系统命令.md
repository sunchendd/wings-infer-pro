# G.EDV.02 禁止使用OS命令解析器或“危险函数”调用系统命令

- **规则ID**：b12654e9-913c-4c40-81d6-f020aa3f5573
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

使用未经校验的不可信输入作为系统命令的参数或命令的一部分，可能导致命令注入漏洞。

因此，执行命令的时候，必须注意以下几点：

1. 命令执行的字符串不要去拼接输入的参数，如果必须拼接时，要对输入参数进行白名单过滤。

2. 对传入的参数要做类型校验，例如：整数数据，可以对数据进行整数强制转换。

3. 对于要求限定格式化字符串类型的业务场景，要保证占位符的正确性。例如：int类型参数的拼接，使用`{:d}`，不能用`{:s}`。

**【正确示例】**

```
##### 场景1：
- 修复示例1：使用系统函数

 ```python
import os
import sys


try:
    # 使用os.listdir来列举目录下的内容
    print(os.listdir(sys.argv[1]))  # 符合
except Exception as ex:
    print(ex)
 ```
- 修复示例2：对外部数据进行校验

```python
import os
import re
import sys


def args_verify(args_list):
    # 校验数据长度
    if len(args_list) > 20:
        print('Parameter length error.')
        sys.exit()
    # 校验数据内容
    if re.match(r"^[.0-9A-Za-z@]+$", args_list[1]):
        return args_list[1]


try:
    # 校验外部数据
    verified_arg = args_verify(sys.argv)
    if verified_arg:
        print(os.system("ls " + verified_arg))  # 符合
except Exception as ex:
    print('exception:', ex)
  ```

```
**【错误示例】**

```
##### 场景1：
- 错误示例：使用os.system直接执行外部命令

```python
import os
import sys


try:
    # 使用os.system直接执行外部命令
    print(os.system("ls " + sys.argv[1]))  # 不符合
except Exception as ex:
    print('exception:', ex)
```

```
**【修复建议】**

1. 尽量使用标准的API替代运行系统命令来完成任务。

2. 如果无法避免使用os.system或os.popen等“危险函数”，则必须要对输入数据进行白名单校验。
