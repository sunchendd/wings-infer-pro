# G.CLS.01 如果子类和父类中都有__init__方法，则子类中的__init__方法必须正确调用其父类__init__方法

- **规则ID**：75b918fb-f7a4-4621-b382-5543629f58e1
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

如果子类和父类都有`__init__`初始化方法，子类其实是重写了父类的`__init__`方法，如果不显式调用父类的`__init__`方法，父类的`__init__`方法就不会被执行，导致子类实例访问父类`__init__`方法中初始化的变量时出现问题，从而导致程序无法达到预期结果。

**【正确示例】**

```
##### 场景1：单继承场景下子类未显式地调用父类的构造方法
- 修复示例：子类调用父类初始化方法
```python
class Base:
    def __init__(self):
        self.base_attr = 1


class Derived(Base):
    def __init__(self):
        super().__init__()  # 符合
        self.derived_attr = 2


if __name__ == '__main__':
    derived_obj = Derived()
    print(derived_obj.base_attr)  
```


```
**【错误示例】**

```
##### 场景1：单继承场景下子类未显式地调用父类的构造方法
- 错误示例：不调用父类初始化方法，导致父类初始化过程遗漏
```python
class Base:
    def __init__(self):
        self.base_attr = 1


class Derived(Base):
    def __init__(self):  # 不符合，未调用基类的构造方法
        self.derived_attr = 2


if __name__ == '__main__':
    derived_obj = Derived()
    print(derived_obj.base_attr)  # AttributeError: 'Derived' object has no attribute 'base_attr'
```


```
**【修复建议】**

在子类中使用`super`类来辅助调用父类的初始化方法。
