# G.EDV.07 不受信任的外部数据禁止使用.format()进行格式化

- **规则ID**：fa73b050-11ec-44b3-8ac1-a3e30dbe28f9
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

严重

**【描述】**

Python 2.6版本引入str.format字符串格式化方法，支持通过string类的format函数处理复杂变量替换以及值的格式化。在使用.format()进行格式化时，如果参数来自不可信任来源的外部数据，这些数据包含恶意代码，就会导致全安漏洞。因此，为了防止代码注入和其他安全问题，最好使用其他方法来格式化外部数据。若不可避免，则需通过白名单或黑名单方式对外部数据进行校验或净化。

**【正确示例】**

```
##### 场景1： 
- 修复示例：格式化前校验外部数据
```python
import re


class User:
    def __init__(self, name, password):
        self.name = name
        self.password = password


def string_verify(input_string):
    # 数字或字母组成的6位输入（可根据具体场景定制合法输入正则表达式）
    pattern_safety = '^[0-9a-zA-z]{6}$'
    compile_pattern = re.compile(pattern_safety)
    if compile_pattern.match(input_string):
        return True
    return False


user = User('admin', 'password@123')
user_input = input('Please input something:')
# 对外部数据进行校验
if string_verify(user_input):
    data_format = user_input.format(u=user)  # 符合
```

```
**【错误示例】**

```
##### 场景1： 
- 错误示例：直接对外部数据进行格式化
```python
class User:
    def __init__(self, name, password):
        self.name = name
        self.password = password


user = User('admin', 'password@123')
user_input = input('Please input something:')
# 直接对外部数据进行格式化
data_format = user_input.format(u=user)  # 不符合
```

```
**【修复建议】**

禁止使用.format()对不受信任的外部数据进行格式化，若不可避免，则需通过白名单或黑名单方式对外部数据进行校验或净化。
