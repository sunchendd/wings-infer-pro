# G.NAM.03“self”应是实例方法的第一个参数，“cls”应是类方法的第一个参数

- **规则ID**：d885e83e-728a-498e-8a26-9ef42fece042
- **更新时间**：2026-04-07 04:15:00

---

**【问题级别】**

一般

**【描述】**

实例方法的第一个参数是“self”，类方法（被@classmethod装饰的函数）的第一个参数是“cls”，这是Python语言常规约定。虽然也可以使用任意形参名字来代替“self”或“cls”，但这会破坏常规约定，从而降低代码的可读性。

**【正确示例】**

```
# 【正例1】
class Student:
    def set_information(self, name, age, sex):  # 符合，实例方法的第一个参数是self
        print("student information")

    def add_information(self, rank):  # 符合，实例方法的第一个参数是self
        print(rank)

# 【正例2】
class Student:
    @classmethod
    def total(cls):   # 类方法total的第一个位置参数是cls
        print("total count")

```
**【错误示例】**

```
# 【反例1】
class Student:
    def set_information(student, name, age, sex):  # 不符合，实例方法中使用student代替self，可读性降低
        print("student information")

    def add_information(rank):  # 不符合，该实例方法忘记写self参数
        print(rank)


if __name__ == '__main__':
    monitor = Student()
    monitor.set_information('lucy', 18, 0)  # 调用成功
    monitor.add_information(1)  # 调用实例方法出错

# 【反例2】
class Student:
    def set_information(self, name, age, sex):  # 符合，实例方法的第一个参数是self
        print("student information")

    def add_information(self, rank):  # 符合，实例方法的第一个参数是self
        print(rank)

```
**【修复建议】**

类的实例方法至少要有一个位置参数self，类方法也要至少有一个位置参数cls，并且必须是第一个
