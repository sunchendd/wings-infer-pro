# G.ERR.05 使用有明确业务属性的异常类型

- **规则ID**：f8d2f75d-8a3e-4b11-aa48-6d148b8cb3d3
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

如果直接使用`except:`语句，实际捕获的异常是`BaseException`，常常与设计预期不一致，且该问题容易被代码维护人员忽视，会导致程序员无法获知具体的异常类型，从而使代码难以维护和理解。

**【正确示例】**

```
##### 场景1：捕获异常
- 修复示例：捕获具体的异常类型,并将Exception放在最后捕获，用于处理未知异常。
```python
try:
    with open(file_name) as fd:
        ...
# 符合
except FileNotFoundError as e:
    ...
# 符合
except PermissionError as e:
    ...
# 符合
except Exception as e: 
    ...
```

```
**【错误示例】**

```
##### 场景1：捕获异常
- 错误示例：捕获异常未指定异常类型
```python
try:
    ...
    exit(1)
except:  # 不符合，会将exit(1)抛出的SystemExit异常捕获
    ...
```

```
**【修复建议】**

尽量使用具体的异常类型，少使用范围很大的异常类型。
