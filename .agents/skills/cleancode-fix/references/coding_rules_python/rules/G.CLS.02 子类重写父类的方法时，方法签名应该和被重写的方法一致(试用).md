# G.CLS.02 子类重写父类的方法时，方法签名应该和被重写的方法一致(试用)

- **规则ID**：d29362a1-8658-4681-b707-95be277f4d3c
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

一般

**【描述】**

子类重写父类方法时，如果方法签名不一致，则会覆盖父类同名方法的实现。这种重写行为违反了里氏替换原则，使子类丢失了一部分父类功能。因此，建议子类在重写父类方法时，保持与父类同名方法的方法签名一致

**【正确示例】**

```
# 【正例1】
class Base:

    def __init__(self):
        self.base_attr = 1

    def refresh_base_attr(self):
        self.base_attr = 0


class Derived(Base):

    def refresh_base_attr_by_value(self, value):
        self.base_attr = value


if __name__ == '__main__':
    derived_obj = Derived()
    derived_obj.refresh_base_attr()
    derived_obj.refresh_base_attr_by_value(2)
    print(derived_obj.base_attr)  # 2

```
**【错误示例】**

```
# 【反例1】
class Base:

    def __init__(self):
        self.base_attr = 1

    def refresh_base_attr(self):
        self.base_attr = 0


class Derived(Base):

    def refresh_base_attr(self, value):
        self.base_attr = value


if __name__ == '__main__':
    derived_obj = Derived()
    derived_obj.refresh_base_attr()  # TypeError: refresh_base_attr() missing 1 required positional argument: 'value'

```
**【修复建议】**

子类重写父类方法时，方法的参数名称要保持一致，不得任意改动参数名称。
