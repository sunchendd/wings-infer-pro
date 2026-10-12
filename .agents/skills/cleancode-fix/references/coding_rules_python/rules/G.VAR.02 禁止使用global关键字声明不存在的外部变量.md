# G.VAR.02 禁止使用global关键字声明不存在的外部变量

- **规则ID**：71fbcc46-59a9-4d73-b3a5-09e1a94701fe
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

使用`global`关键字声明不存在的外部变量，导致代码可读性差、难以维护，还可能会引发一些不可预知的错误。因此，禁止使用`global`关键字声明不存在的外部变量。

**【正确示例】**

```
##### 场景1：global声明不存在的外部变量
- 修复示例：函数中修改全局变量时，需要使用`global`进行声明
```python
_variable = 1


def test():
    global _variable  # 符合
    _variable = 2


test()
print(_variable)
```


```
**【错误示例】**

```
##### 场景1：global声明不存在的外部变量
- 错误示例：外部作用域中没有全局变量`variable`，在`test`函数内使用`global`创建了全局变量`variable`，这是不好的实践。
```python
def test():
    global variable  # 不符合，不存在全局变量variable
    variable = 1


test()
print(variable)
```
- 错误示例：函数中仅读取全局变量时，不需要使用`global`进行声明。
```Python
_variable = 1


def test():
    global _variable  # 不符合，仅读取全局变量时，不需要使用global进行声明
    print(_variable)


test()
```


```
**【修复建议】**

1. 禁止使用global关键字声明不存在的外部变量。

2. 函数中修改全局变量时，需要使用`global`进行声明，对于仅需要读的场景，不需要使用`global`关键字。
