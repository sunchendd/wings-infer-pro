# G.CTL.01 同一个函数所有分支的返回值类型和个数保持一致

- **规则ID**：96d83c10-7d75-445d-bc58-f989b15f59d2
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

如果同一个函数多个分支返回的对象类型和数量不一致，调用者无法使用统一的类型/逻辑来处理返回值，增加了对不同分支的返回值区分处理的开销以及未来代码修改的风险。因此，要求同一个函数所有分支的返回值类型和个数保持一致。



注：`None`可以作为与自定义对象同类型的返回值，但不能作为内置类型的同类。

**【正确示例】**

```
### 场景1：函数的返回值个数不一致
- 修复示例：包含`if`条件分支，但多分支的返回个数一致。
```python
def function_return_type_inconsistent_next(x):
    if x < 0:
        return -x + 1
    # 符合，返回个数一致
    return x + 1
```
### 场景2：函数的返回值整型不一致
- 修复示例：函数多分支，返回类型一致。
```python
def function_return_type_inconsistent_int(x):
    if x < 0:
        return 0
    # 符合，返回类型一致
    return x + 1
```
### 场景3：函数的返回值字符串类型不一致
- 修复示例：通过返回元祖类型值,来确保返回类型一致
```python
def function_return_type_inconsistent_str(x):
    if x < 0:
        return False, None
    # 符合，返回2个值的元祖, 确保返回类型一致
    return True, 'ok'
```

```
**【错误示例】**

```
### 场景1：函数的返回值个数不一致
- 错误示例：下面的函数都包含`if`条件分支，但多分支的返回个数不一致。
```python
def function_return_type_inconsistent_next(x):
    if x < 0:
        return 0, -x + 1
    # 不符合，返回个数不一致
    return x + 1

```
### 场景2：函数的返回值整型不一致
- 错误示例：函数多分支，有返回整数类型，有返回None
```python
def function_return_type_inconsistent_int(x):
    if x < 0:
        return None
    # 不符合，返回类型不一致
    return x + 1
```
### 场景3：函数的返回值字符串类型不一致
- 错误示例：函数多分支，有返回字符串类型，有返回None
```python
def function_return_type_inconsistent_str(x):
    if x < 0:
        return None
    # 不符合，返回类型不一致
    return 'ok'
```

```
**【修复建议】**

同一个函数所有分支的返回值类型和个数保持一致。
