# G.FNM.04 不要将没有返回值的函数调用结果赋值给变量

- **规则ID**：476952a6-7843-4c48-a264-593dc358f32a
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

将没有返回值的函数调用赋值给变量时，变量实际被赋值为None，没有意义，会导致代码冗余。

**【正确示例】**

```
##### 场景1：没有返回值的函数赋值给变量
- 修复示例：有返回值的函数赋值给变量
```python
def division_if_success_return_true(x, y):
    try:
        print(x / y)
    except ZeroDivisionError:
        return False
    return True


# 符合，函数返回值赋值给变量
result = division_if_success_return_true(1, 2)
```

```
**【错误示例】**

```
##### 场景1：没有返回值的函数赋值给变量
- 错误示例：没有返回值的函数赋值给变量
```python
def division(x, y):
    try:
        print(x / y)
    except ZeroDivisionError:
        print('除数不能为0')


# 不符合，函数没有返回值
result = division(1, 2)
```

```
**【修复建议】**

不要将没有返回值的函数调用结果赋值给变量。
