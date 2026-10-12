# G.FNM.05 当函数返回值个数较多时，建议通过class/namedtuple/dataclass等具名形式进行封装

- **规则ID**：98b172f8-b63d-4bbe-848b-a172f73ef71d
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

函数返回值过多，会导致代码可读性差，代码复杂度增加，难以理解。

**【正确示例】**

```
##### 场景1：函数返回值个数较多
- 修复示例：采用类进行数据封装
```python
class Student:
    def __init__(self, name, age, gender, height=None, weight=None, education=None, religion=None):
        self.name = name
        self.age = age
        self.gender = gender
        self.height = height
        ...


def get_student_info(id):
    # get info from database
    ...
    # 符合，返回值使用类封装
    student = Student("bob", 19, "male")
    return student
```
- 修复示例：采用具名元组进行数据封装
```python
import collections

Student = collections.namedtuple("Student", ["name", "age", "gender", "height", "weight", "education", "religion"])


def get_student_info(id):
    # get info from database
    ...
    # 符合，返回值使用元组封装
    student = Student("bob", 12, "male", None, None, None, None)
    return student
```
- 修复示例：采用dataclass进行数据封装
```python
from dataclasses import dataclass


@dataclass
class Student:
    name: str
    age: int
    gender: str
    height: int


def get_student_info(id):
    # get info from database
    ...
    # 符合，返回值使用dataclass封装
    student = Student("jack", 18, "male", 170)
    return student
```

```
**【错误示例】**

```
##### 场景1：函数返回值个数较多
- 错误示例：函数返回值超过3个
```python
def get_student_info(id):
    # get info from database
    ...
    # 不符合，函数返回值超过3个
    return name, age, gender, height, weight, education, religion
```

```
**【修复建议】**

函数返回值最好不要超过3个，超过时通过class/namedtuple/dataclass等具名形式进行封装。
