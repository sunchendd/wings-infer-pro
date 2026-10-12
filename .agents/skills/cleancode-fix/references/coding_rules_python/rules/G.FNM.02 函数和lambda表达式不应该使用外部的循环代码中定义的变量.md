# G.FNM.02 函数和lambda表达式不应该使用外部的循环代码中定义的变量

- **规则ID**：3fe6b327-b94c-4247-ad4c-cbfdbfb8aebd
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

如果在循环体中定义了函数/lambda并引用了循环变量，则在循环体外调用该函数时，将始终获取到该循环变量的终值，导致结果与预期不一致。

**【正确示例】**

```
##### 场景1：lambda表达式使用外部循环变量
- 修复示例：如果在循环中立即调用函数或使用lambda表达式，而不是循环结束之后才调用或使用，可以在函数或lambda表达式中使用外部循环中的变量。
下述代码示例中，list是强制进行计算并转为list格式，是立即执行的。
```python
for i in range(5):
    print(list(map(lambda j: i + j, range(5))))  # 符合


执行结果：
 [0, 1, 2, 3, 4]
 [1, 2, 3, 4, 5]
 [2, 3, 4, 5, 6]
 [3, 4, 5, 6, 7]
 [4, 5, 6, 7, 8]
```
##### 场景2：函数中使用外部循环变量
- 修复示例：嵌套函数不引用循环变量，将函数与参数值同时保存，形成[(函数,参数)]的映射列表。
```python
def test():
    """循环打印出0到4"""
    func_list = []
    def func(value):
        return value

    for i in range(5):
        func_list.append((func, i)  # 符合

    for func, arg in func_list:
        print(func(arg))


test()
```

```
**【错误示例】**

```
##### 场景1：lambda表达式使用外部循环变量
- 错误示例：第一个for循环使用的是map，map是延期执行的
```python
map_list = []
for i in range(5):
    # 不符合，循环中使用lambda，延迟调用
    map_list.append(map(lambda j: i + j, range(5)))

for unit in map_list:
    print(list(unit))


执行结果：
[4, 5, 6, 7, 8]
[4, 5, 6, 7, 8]
[4, 5, 6, 7, 8]
[4, 5, 6, 7, 8]
[4, 5, 6, 7, 8]
```
##### 场景2：函数中使用外部循环变量
- 错误示例：嵌套函数中采用了外部循环体的循环变量。
代码本意：循环打印出0~4
实际结果：重复打印4
```python
def test():
    """循环打印出0到4"""
    func_list = []
    for i in range(5):
        def func():
            return i  # 不符合

        func_list.append(func)

    for func in func_list:
        print(func())


test()
```

```
**【修复建议】**

lambda表达式不能引用循环变量，如果在循环中立即调用函数或使用lambda表达式，而不是循环结束之后才调用或使用，可以在函数或lambda表达式中使用外部循环中的变量。
