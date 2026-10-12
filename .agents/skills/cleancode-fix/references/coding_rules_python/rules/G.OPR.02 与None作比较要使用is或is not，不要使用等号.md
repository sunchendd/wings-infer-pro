# G.OPR.02 与None作比较要使用is或is not，不要使用等号

- **规则ID**：cfd69b67-0c98-4f04-8391-bd2a9c99e3d6
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

`is`判断是否指向同一个对象（判断两个对象的id是否相等），`==`会调用`__eq__`方法判断是否等价（判断两个对象的值是否相等）。None是python中的一个特殊的常量，表示一个空的对象。一个变量如果是None，它一定和None指向同一个内存地址。因此，判断实例为None时，与None作比较应该使用`is`或`is not`。



注意：None和空值不是一个东西，空值是Python中的一个特殊值，数据为空并不代表是空对象，例如`[]`, `{}`, `()`, `''`等都不是None。

**【正确示例】**

```
##### 场景1：对象与None的比较
- 修复示例：同一个实例，使用`is`和`==`的判断结果不同
```python
class PersonMetaClass(object):
    def __init__(self, name, age, gender):
        self.name = name
        self.age = age
        self.gender = gender

    def __eq__(self, other):
        if hasattr(other, 'gender'):
            return self.gender == other.gender
        else:
            return 'The assertion property does not exist'


student1 = PersonMetaClass('Xiao li', 17, 'female')
student2 = PersonMetaClass('Han Hong', 18, 'female')
print(student2 is None)  # 符合，判断两个对象的id是否相等，结果为False
print(student2 is student1)  # False
```


```
**【错误示例】**

```
##### 场景1：对象与None的比较
- 错误示例：对象与None用等于号做比较
```python
class PersonMetaClass(object):
    def __init__(self, name, age, gender):
        self.name = name
        self.age = age
        self.gender = gender

    def __eq__(self, other):
        if hasattr(other, 'gender'):
            return self.gender == other.gender
        else:
            return 'The assertion property does not exist'


student1 = PersonMetaClass('Xiao li', 17, 'female')
student2 = PersonMetaClass('Han Hong', 18, 'female')
print(student2 == None)  # 不符合，判断两个对象的值是否相等，结果为The assertion property does not exist
print(student2 == student1)  # True
```


```
**【修复建议】**

与None作比较要使用`is`或`is not`。
