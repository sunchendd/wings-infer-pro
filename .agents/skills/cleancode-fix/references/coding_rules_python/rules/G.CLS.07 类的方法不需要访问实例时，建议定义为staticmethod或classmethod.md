# G.CLS.07 类的方法不需要访问实例时，建议定义为staticmethod或classmethod

- **规则ID**：394020f8-a0de-494d-a1c4-b906b0fe5216
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

类的方法不需要访问实例时，使用普通的实例方法定义虽然可以实现功能，但会在使用时要求必须由类的实例调用此方法。这就造成使用过程中一次冗余的实例生成、回收过程，代码本身编写和阅读时也显得冗余。

**【正确示例】**

```
##### 场景1：类的方法不需要访问实例
- 修复示例：类方法不需要访问类实例，使用classmethod或者staticmethod
```python
class MyClass:
    class_attr = "MyClass.class_attr"

    @classmethod
    def refresh_class_attr(cls, string_value: str):  # 符合
        cls.class_attr = string_value

    @staticmethod
    def add(a: int, b: int) -> int:  # 符合
        return a + b


if __name__ == '__main__':
    MyClass.refresh_class_attr("Refreshed MyClass.class_attr")
    print(MyClass.class_attr)  # "Refreshed MyClass.class_attr"
    print(MyClass.add(1, 2))  # 3
```


```
**【错误示例】**

```
##### 场景1：类的方法不需要访问实例
- 错误示例：
```python
class MyClass:
    class_attr = "MyClass.class_attr"
    
    def refresh_class_attr(self, string_value: str):  # 不符合，在不需要访问实例，需要访问类属性或方法
        MyClass.class_attr = string_value

    def add(self, a: int, b: int) -> int:  # 不符合，不需要访问实例也不需要访问类属性或方法
        return a + b


if __name__ == '__main__':
    MyClass().refresh_class_attr("Refreshed MyClass.class_attr")
    print(MyClass.class_attr)  # "Refreshed MyClass.class_attr"
    print(MyClass().add(1, 2))  # 3
```


```
**【修复建议】**

1. 在不需要访问实例，需要访问类属性或方法时，建议使用`@classmethod`将方法定义为类方法；

2. 在不需要访问实例也不需要访问类属性或方法时，建议使用`@staticmethod`将方法定义为静态方法。
