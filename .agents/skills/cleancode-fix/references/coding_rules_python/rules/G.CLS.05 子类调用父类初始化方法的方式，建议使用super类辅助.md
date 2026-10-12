# G.CLS.05 子类调用父类初始化方法的方式，建议使用super类辅助

- **规则ID**：33b1b766-2366-4953-a8e5-16d4ee72bfc3
- **更新时间**：2026-04-07 04:15:00

---

**【问题级别】**

一般

**【描述】**

Python中子类调用父类初始化方法一般有以下两种方式：



- 使用父类类名`ClassName.__init__(self)`的方式，这种写法比较清晰易懂，但是与父类类名绑定，而且在菱形继承场景下顶层父类初始化函数会被调用多次。

- 使用`super`类的方式调用父类初始化方法，这种写法不与父类类名绑定，且可以保证菱形继承场景下，创建一个子类对象仅调用顶层父类初始化函数一次。



因此，子类调用父类初始化方法的方式建议使用`super`类。

**【正确示例】**

```
##### 场景1：菱形继承场景
- 修复示例：使用super代替类名调用
```python
class Ancestor:
    def __init__(self, **kwargs):
        print("ancestor initialize invoked")


class Base(Ancestor):
    def __init__(self, base_attr, **kwargs):
        super().__init__(**kwargs)  # 符合
        self.base_attr = base_attr


class BaseTwo(Ancestor):
    def __init__(self, base_two_attr, **kwargs):
        super().__init__(**kwargs)  # 符合
        self.base_two_attr = base_two_attr


class Derived(Base, BaseTwo):
    def __init__(self, base_attr, base_two_attr, derived_attr, **kwargs):
        super().__init__(base_attr=base_attr, base_two_attr=base_two_attr, **kwargs)  # 符合
        self.derived_attr = derived_attr


if __name__ == '__main__':
    derived_obj = Derived(base_attr=1, base_two_attr=2, derived_attr=3)  # ancestor initialize invoked
    print(derived_obj.base_attr) 
    print(derived_obj.base_two_attr) 
    print(derived_obj.derived_attr) 
```


```
**【错误示例】**

```
##### 场景1：菱形继承场景
- 错误示例：如果直接使用类名调用`__init__`方法，将造成Ancestor类的初始化方法被调用两次
```python
class Ancestor:
    def __init__(self):
        print("ancestor initialize invoked")


class Base(Ancestor):
    def __init__(self, base_attr):
        Ancestor.__init__(self)  # 不符合，未使用super方式调用基类方法
        self.base_attr = base_attr


class BaseTwo(Ancestor):
    def __init__(self, base_two_attr):
        Ancestor.__init__(self)  # 不符合，未使用super方式调用基类方法
        self.base_two_attr = base_two_attr


class Derived(Base, BaseTwo):
    def __init__(self, base_attr, base_two_attr, derived_attr):
        Base.__init__(self, base_attr)
        BaseTwo.__init__(self, base_two_attr)
        self.derived_attr = derived_attr


if __name__ == '__main__':
    derived_obj = Derived(1, 2, 3)  # "ancestor initialize invoked" will print twice.
    print(derived_obj.base_attr)  # 1
    print(derived_obj.base_two_attr)  # 2
    print(derived_obj.derived_attr)  # 3
```


```
**【修复建议】**

子类调用父类初始化方法的方式建议使用`super`类辅助。
