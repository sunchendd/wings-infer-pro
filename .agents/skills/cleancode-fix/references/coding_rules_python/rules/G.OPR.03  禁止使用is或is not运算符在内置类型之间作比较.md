# G.OPR.03  禁止使用is或is not运算符在内置类型之间作比较

- **规则ID**：93cae55e-4a9f-43df-ad90-e4fdcfc6fd00
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

`is`和`is not`是用来检查两个实例是否引用同一个对象的，禁止用`is`或`is not`运算符在内置类型之间作比较，否则程序会出现`SyntaxWarning`语句警告信息：`SyntaxWarning: "is" with a literal. Did you mean "=="?`。内置类型有int、float、complex、list、tuple、set、frozenset、dict、str、bytes，建议用`==`或`!=`运算符替代。针对于内置类型比较地址的情况，建议使用`id()`判断代替`is`和`is not`。

**【正确示例】**

```
##### 场景1：内置类型之间作比较
- 修复示例：
```python
def literal_comparison(param):
    return param == 2000   # 符合，整数比较用==


literal_comparison(2000)  # True
literal_comparison(int("2000"))  # True
print(() == tuple())  # 符合，元组比较用==，结果为True
print((1,) == tuple([1]))  # 符合，元组比较用==，结果为True
```


```
**【错误示例】**

```
##### 场景1：内置类型之间作比较
- 错误示例：
```python
def literal_comparison(param):
    return param is 2000   # 不符合，整数比较用is


literal_comparison(2000)  # True
literal_comparison(int("2000"))  # False
print(() is tuple())  # 不符合，元组比较用is，结果为True
print((1,) is tuple([1]))  # 不符合，元组比较用is，结果为False
```


```
**【修复建议】**

内置类型数值之间用`==`或`!=`来比较。
