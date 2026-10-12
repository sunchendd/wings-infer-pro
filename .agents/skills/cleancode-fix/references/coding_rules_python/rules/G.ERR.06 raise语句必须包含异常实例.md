# G.ERR.06 raise语句必须包含异常实例

- **规则ID**：93478f46-b5cc-4927-8f5c-295b45225465
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

使用`raise`语句时，Python会查找被`except`语句捕获的最后一个异常，如果不存在对应的异常（即没有`except`语句），抛出的异常类型为`RuntimeError`，丢失了原始错误调用栈信息，从而会导致代码错误难以定位。

**【正确示例】**

```
##### 场景1：捕获异常
- 修复示例：raise语句抛出异常实例。
```python
try:
    ...
except UserDefined.UnrecoverableException as e:
    do_something(e)
    raise  # 符合，重新抛出异常UserDefined.UnrecoverableException
```
- 修复示例：raise语句抛在except语句范围内。
```python
try:
    ...
except UserDefined.UnrecoverableException as e:
    do_something(e)
    raise e  # 符合，重新抛出异常UserDefined.UnrecoverableException
```

```
**【错误示例】**

```
##### 场景1：捕获异常
- 错误示例：单使用raise抛出异常,后面不接异常类型，并且不在except语句范围内
```python
raise  # 不符合，会抛出RuntimeError
```

```
**【修复建议】**

raise语句抛出异常实例，或者在except语句范围内。
