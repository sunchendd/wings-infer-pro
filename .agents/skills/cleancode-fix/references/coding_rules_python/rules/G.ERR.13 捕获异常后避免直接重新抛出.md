# G.ERR.13 捕获异常后避免直接重新抛出

- **规则ID**：4c8cf008-f5bf-4a3e-9fc4-faee22d3bd54
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

`except`语句在捕获异常后，避免直接重新抛出，捕获并重新抛出异常与不写`except`语句没区别，这些无效的逻辑影响了代码的可读性。

**【正确示例】**

```
##### 场景1：抛出捕获异常
- 修复示例：同时使用多个`except`语句时，如果需要对某个异常子类做特殊处理，需要加必要的注释
```python
try:
    1 / 0
except ZeroDivisionError:
    # 符合，除0异常需要外抛，由调用者捕获并处理
    raise
except Exception as e:
    do_something(e)
```

```
**【错误示例】**

```
##### 场景1：抛出捕获异常
- 错误示例：捕获异常后直接抛出
```python
try:
    do_something()
except SomeException:
    raise    # 不符合
except Exception as e:
    do_something(e)
```

```
**【修复建议】**

捕获异常后抛出新异常或者调用函数进行异常处理。
