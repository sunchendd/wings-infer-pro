# G.TYP.08 必须使用isinstance判断变量类型

- **规则ID**：854e9109-85f0-432c-bb47-b631c5ed5268
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

使用`isinstance`代替`type`比较来判断自定义变量类型，可以处理更多的类型，比如类继承等，比`type`比较来判断的更准确。

判断基础类型时，使用`isinstance`和`type`均可，并无太大区别。

**【正确示例】**

```
### 场景1：判断对象类型
- 修复示例：使用`isinstance`判断对象类型
```python
is_integer = isinstance(obj, int)          # 符合
is_integer_or_float = isinstance(obj, (int, float))   # 符合


class B:
     pass


class C(B):
     pass


isinstance(C(), B)   # 符合


class ABC(type):
    def __instancecheck__(cls, inst):
        return any(cls.__subclasscheck__(c)
                   for c in {type(inst), inst.__class__})

    def __subclasscheck__(cls, sub):
        candidates = cls.__dict__.get("__subclass__", set()) | {cls}
        return any(c in candidates for c in sub.mro())


class Integer(metaclass=ABC):
    __subclass__ = {int}


isinstance(1, Integer)   # 符合
```
### 场景2：区分bool和int类型
- 修复示例：使用`type`区分bool和int类型
```python
ret = True 
type(ret) == int # 符合，返回的是false
type(ret) == bool # 符合，返回的是true
```
### 场景3：判断2个对象是否同一类型
- 修复示例：使用`isinstance`判断对象类型
```python
class A:
    pass
class B(A):
    pass
    
a1 = A()
b1 = B()
if isinstance(b1, type(a1)):  # 符合
    pass
```

```
**【错误示例】**

```
### 场景1：判断对象类型
- 错误示例：使用type判断对象类型
```python
is_integer = type(obj) is type(1)   # 不符合
```
### 场景2：区分bool和int类型
- 错误示例：使用isinstance区分bool和int类型
```python
ret = True 
isinstance(ret,int) # 不符合，返回的是true
```
### 场景3：判断2个对象是否同一类型
- 错误示例：试用type判断类型相等
```python
class A:
    pass
class B(A):
    pass
    
a1 = A()
b1 = B()
if type(a1) == type(b1): # 不符合
    pass
```

```
**【修复建议】**

自定义类型使用isinstance而不是type来判断变量类型，基础类型使用`isinstance`和`type`均可。

当需要区分bool和int类型时，不能使用`isinstance`，必须使用`type`。
