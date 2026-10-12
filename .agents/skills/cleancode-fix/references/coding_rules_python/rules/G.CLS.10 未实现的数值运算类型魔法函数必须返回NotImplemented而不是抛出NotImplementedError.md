# G.CLS.10 未实现的数值运算类型魔法函数必须返回NotImplemented而不是抛出NotImplementedError

- **规则ID**：2416e292-c6b5-41e9-8078-1c678d27a53c
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

数值运算类型的魔法函数（如`__eq__()`，`__lt__()`，`__add__()`，`__rsub__()`等）在有定义却无具体实现时返回`NotImplemented`，而不是抛出`NotImplementedError`异常。否则会导致程序出现未知的运行结果。

**【正确示例】**

```
##### 场景1：重写数值运算魔法函数
- 修复示例： 在`a == b`的比较中解释器会先调用`a.__eq__`，发现`a.__eq__`方法返回`NotImplemented`后，会调用`b.__eq__`方法来完成功能
```python
class Entity:
    def __init__(self, eid=0):
        self.eid = eid


class EntityA(Entity):
    def __eq__(self, other):
        return NotImplemented  #  符合


class EntityB(Entity):
    def __eq__(self, other):
        return self.eid == other.eid


if __name__ == '__main__':
    a = EntityA(eid=1)
    b = EntityB(eid=2)
    print(a == b)  # False
```

```
**【错误示例】**

```
##### 场景1：重写数值运算魔法函数
- 错误示例：  在魔法函数中抛出NotImplementedError
```python
class Entity:
    def __init__(self, eid=0):
        self.eid = eid


class EntityA(Entity):
    def __eq__(self, other):
        raise NotImplementedError()  #  不符合


class EntityB(Entity):
    def __eq__(self, other):
        return self.eid == other.eid


if __name__ == '__main__':
    a = EntityA(eid=1)
    b = EntityB(eid=2)
    print(a == b)  # NotImplementedError
```

```
**【修复建议】**

未实现的数值运算类型魔法函数返回`NotImplemented`而不是抛出`NotImplementedError`。
