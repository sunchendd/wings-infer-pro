# G.FNM.03 当函数参数个数较多且有相关性时，建议通过class/namedtuple/dataclass等具名形式进行封装

- **规则ID**：bc53ed27-16c1-4db0-bd4e-25130db282e3
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

函数参数过多，会导致代码可读性差，难以理解。

**【正确示例】**

```
##### 场景1：函数参数个数较多
- 修复示例：采用dataclass进行数据封装，适用于Python3.7以上版本
```python
from dataclasses import dataclass


@dataclass
class Student:
    name: str
    age: int
    gender: str
    height: int


#  符合，函数参数过多，使用dataclass进行封装
def process_student_info(student):
    print(student.name)


freshman = Student("nn", 12, "male", None)
process_student_info(freshman)
```
- 修复示例：采用具名元组进行数据封装
```python
import collections

Student = collections.namedtuple('Student', ['name', 'age', 'gender', 'height', 'weight', 'education', 'religion'])


# 符合，函数参数过多，使用namedtuple进行封装
def process_student_info(student):
    # do something here
    ...


freshmen = Student("bob", 12, "male", None, None, None, None)
process_student_info(freshmen)
```
- 修复示例：采用类进行数据封装
```python
class Student:
    def __init__(self, name, age, gender, height=None, weight=None, education=None, religion=None): 
        self.name = name
        self.age = age
        self.gender = gender
        self.height = height
        ...


# 符合，函数参数过多，使用类进行封装
def add_freshmen(student):
    # do something here
    ...


freshmen = Student("bob", 19, "male")
add_freshmen(freshmen)
```

```
**【错误示例】**

```
##### 场景1：函数参数个数较多
- 错误示例：函数参数超过5个
```python
#  不符合，函数参数超过5个
def add_freshmen(name, age, gender, height, weight, education, religion):
    ...


#  不符合，函数参数超过5个
add_freshmen("bob", 19, "male", None, None, None, None)
```

```
**【修复建议】**

当函数参数个数较多(一般多于5个)，并且参数之间有一定相关性时，建议通过class/namedtuple(具名元组)/dataclass等具名形式进行封装。
