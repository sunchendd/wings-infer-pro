# G.PSL.04 建议用functools.wraps定义函数装饰器

- **规则ID**：076c1f85-a0fe-4a09-a041-d8606a4e6084
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

一般的装饰器写法在功能上虽然没有问题，但是会导致被装饰函数对象的内部属性发生变化，造成了后续使用上的不便。

因此，建议在装饰器的书写过程中，使用`functools.wraps`的写法定义函数装饰器，避免被装饰函数内部属性被破坏。

**【正确示例】**

```
##### 场景1：使用函数装饰器
- 修复示例：使用functools.wraps定义函数装饰器
```python
from functools import wraps


def my_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):    # 符合
        print("call decorated function")
        return func(*args, **kwargs)

    return wrapper


@my_decorator
def example():
    """this is example docstring"""
    print("call example function")


example()
print(example.__name__)  # example
print(example.__doc__)  # this is example docstring
```

```
**【错误示例】**

```
##### 场景1：使用函数装饰器
- 错误示例：如下一般的装饰器写法将会改写被装饰函数的部分属性，导致`__name__`，`__doc__`等内部属性产生混乱
```python
def my_decorator(func):
    def wrapper(*args, **kwargs):      # 不符合
        print("call decorated function")
        return func(*args, **kwargs)

    return wrapper


@my_decorator
def example():
    """this is example docstring"""
    print("call example function")


example()
print(example.__name__)  # wrapper
print(example.__doc__)  # None
```

```
**【修复建议】**

用functools.wraps定义函数装饰器。
