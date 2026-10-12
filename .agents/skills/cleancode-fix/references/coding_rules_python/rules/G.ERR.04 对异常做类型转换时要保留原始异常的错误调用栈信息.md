# G.ERR.04 对异常做类型转换时要保留原始异常的错误调用栈信息

- **规则ID**：6a04df21-c46f-49ec-9460-b657cf78c852
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

如果需要对异常类型进行转换，建议保留原始异常的错误调用栈信息。如果丢失了错误调用栈信息，会给问题定位、运维等带来不必要的麻烦，会导致代码难以维护。

**【正确示例】**

```
##### 场景1：异常抛出
- 修复示例：使用raise from语句来保留原始异常的错误调用栈。
```python
try:
    with open(file_name) as fd:
        ...
except OSError as e:
    # 符合
    raise UserDefined.InvalidFile('Please check file name') from e
```

```
**【错误示例】**

```
##### 场景1：异常抛出
- 错误示例：丢失了错误调用栈，无法判断具体异常是PermissionError还是FileNotFoundError。
```python
try:
    with open(file_name) as fd:
        ...
except OSError:
    # 不符合，抛出异常丢失了具体异常信息
    raise UserDefined.InvalidFile('Please check file name')
```

```
**【修复建议】**

使用raise from语句来保留原始异常的错误调用栈信息。
