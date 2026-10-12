# G.EXP.01 尽可能使用隐式布尔值

- **规则ID**：7396672d-5ef6-40e6-aaad-8910618284bc
- **更新时间**：2026-04-07 04:15:00

---

**【问题级别】**

一般

**【描述】**

Python可以对所有的对象进行隐式布尔值的推断，Python的官方文档中提到以下对象会被看作False：



常量None 和 False

值为0的数值类型：0, 0.0, 0j，decimal.Decimal(0), fractions.Fraction(0,1)

空的序列和容器类型：'',(),[],{},set(),range(0)以及range(8,5)类似的情况

该对象的类定义了__bool__方法，且该方法返回False

否则，该对象的类定义了__len__方法，且该方法返回0

因此，在选择结构的条件表达式中，尽可能使用隐式布尔值。

**【正确示例】**

```
def implicit_false(mydata):
    if mydata:
        pass
    else:
        pass

```
**【错误示例】**

```
def implicit_false(mydata):
    if mydata != []:
        pass
    else:
        pass

```
**【修复建议】**

尽可能使用隐式布尔值。
