# G.ERR.12 合理地使用object.__exit__处理异常

- **规则ID**：074a31e0-7cfa-4ce8-aa6b-e9aedd426b07
- **更新时间**：2026-04-07 04:15:00

---

**【问题级别】**

一般

**【描述】**

Python的对象支持定义`__enter__`与`__exit__`方法以实现上下文管理，`__exit__`定义的是对象退出时要执行的代码块。`__exit__`如果不能正确的返回值，会导致对象退出功能出现异常。

**【正确示例】**

```
##### 场景1：实现`__exit__`方法
- 修复示例：在实现`__exit__`方法时，返回`True`
```python
import contextlib


class SuppressAllExceptions(contextlib.AbstractContextManager):
    """屏蔽所有异常"""

    def __exit__(self, exc_type, exc_value, traceback):
        return True  # 符合


with SuppressAllExceptions():
    raise IOError()  # 这里抛出的异常会被屏蔽
```

```
**【错误示例】**

```
##### 场景1：实现`__exit__`方法
- 错误示例：在实现`__exit__`方法时，返回整数
```python
import contextlib


class NegativeExample(contextlib.AbstractContextManager):
    def __exit__(self, exc_type, exc_value, traceback):
        ...
        return 1  # 不符合，返回的类型不属于True/False/None
```

```
**【修复建议】**

在实现`__exit__`方法时，要明确对异常的处理方式：

1. 如果要屏蔽某个异常，必须返回`True`

2. 如果要某个异常保持外抛，返回`False`或`None`

3. 如果要抛出新的异常，执行`raise X()`
