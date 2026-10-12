# G.FNM.01 禁止使用可变对象作为参数默认值

- **规则ID**：934c3427-f887-46a2-b1f2-840f1e45fb9d
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

在Python程序中，函数的参数默认值只会被初始化一次，并且被重复利用，当参数默认值为可变对象时，若函数调用时不传入参数值，则对该参数的默认值进行的任何操作实际上操作的是同一个对象，这可能会引发一些不可预知的错误。

**【正确示例】**

```
##### 场景1：函数列表参数
- 修复示例：使用None作为默认值，在程序中重新初始化为空列表
```python
#  符合，函数参数使用None作为默认值，在函数体中初始化列表
def fun(arg_a, list_arg=None):
    list_arg = list_arg or []
    list_arg.append(arg_a)
    print(list_arg)


fun(1)  # 打印[1]
fun(1)  # 打印[1]
fun(1, [])  # 打印[1]
fun(1, {})  # 打印[1]
fun(1, ())  # 打印[1]
fun(1, False)  # 打印[1]
```
##### 场景2：函数字典参数
- 修复示例：使用None作为默认值，在程序中重新初始化为空字典
```python
# 符合，函数参数使用None作为默认值，在函数体中初始化字典
def fun(arg_a, list_arg=None):
    list_arg = {} if list_arg is None else list_arg
    list_arg[arg_a] = arg_a
    print(list_arg)
```

```
**【错误示例】**

```
##### 场景1：函数列表参数
- 错误示例：使用空列表作为默认值 
```python
# 不符合，函数参数使用空列表作为默认值
def fun(arg_a, list_arg=[]):
    list_arg.append(arg_a)
    print(list_arg)


fun(1)      # 打印[1]
fun(1)      # 打印[1, 1]
fun(1, [])  # 打印[1]
```
##### 场景2：函数字典参数
- 错误示例：使用空字典作为默认值
```python
# 不符合，函数参数使用空字典作为默认值
def fun(arg_a, list_arg={}):
    list_arg[arg_a] = arg_a
    print(list_arg)


fun(1)      # 打印{1: 1}
fun(2)      # 打印{1: 1, 2: 2}
fun(3, {})  # 打印{3: 3}
```

```
**【修复建议】**

仅可使用不可变对象作为参数默认值，例如：bool、int、float、complex、tuple、str、bytes、frozenset、None。
