# G.CLS.06 类的方法建议统一按照一种规则进行排列

- **规则ID**：cbdc6266-6074-4adf-b758-02c1eec33254
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

按照业界约定俗成的顺序来组织类的方法，否则会导致代码可读性差，代码组织结构混乱。

**【正确示例】**

```
##### 场景1：staticmethod和classmethod方法的顺序
- 修复示例：staticmethod和classmethod定义在__init__方法之后，并且staticmethod在classmethod之前
```python
class A(object):
    def __init__(self):  #  符合
        self.name = 'huawei_rule'

    @staticmethod
    def sample_static_method():
        print('called')

    @classmethod
    def sample_cls_method(cls):
        cls.sample_static_method()
```


```
**【错误示例】**

```
##### 场景1：staticmethod和classmethod方法的顺序
- 错误示例：staticmethod和classmethod定义在__init__方法之前
```python
class A(object):
    @classmethod
    def sample_cls_method(cls):
        cls.sample_static_method()

    @staticmethod
    def sample_static_method():
        print('called')
    
    def __init__(self):  #  不符合
        self.name = 'huawei_rule'
```


```
**【修复建议】**

建议类的多个方法按照如下的顺序组织：

1. `__new__`静态方法

2. `__init__`方法

3. `__post_init__`方法

4. 其它魔法函数

5. `@property`修饰的对象属性

6. `@staticmethod`修饰的静态方法

7. `@classmethod`修饰的类方法

8. 普通方法

9. 保护方法或私有方法
