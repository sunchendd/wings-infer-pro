# G.ERR.10 同时使用多个except语句时，要注意异常捕获的顺序

- **规则ID**：ce85033c-f44a-462c-8563-b293d20722d0
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

对于同一个`try`语句，支持配对多个`except`语句，按照`except`语句的次序捕获对应的异常。

捕获异常A的语句应该放在其父类之前。如果先捕获异常A的父类，因为对应的异常已经被处理，则捕获异常A的语句不会被执行，会导致产生永远不会被执行的代码块。

**【正确示例】**

```
##### 场景1：捕获父子异常
- 修复示例：先捕获子异常类型，再捕获父异常类型
```python
try:
    with open(file_name) as fd:
        ...
except (FileNotFoundError, PermissionError) as e:   # 符合
    do_something(e)
except Exception as e:   # 符合
    do_otherthing(e)
```

```
**【错误示例】**

```
##### 场景1：捕获父子异常
- 错误示例：先捕获父异常类型，再捕获子异常类型
```python
try:
    with open(file_name) as fd:
        ...
except OSError as e:
    do_something(e)
except FileNotFoundError as e:  # 不符合，FileNotFoundError继承自OSError，该代码块永远不会被执行
    do_otherthing(e)
```

```
**【修复建议】**

注意异常捕获的顺序，先捕获子异常类型，再捕获父异常类型。
