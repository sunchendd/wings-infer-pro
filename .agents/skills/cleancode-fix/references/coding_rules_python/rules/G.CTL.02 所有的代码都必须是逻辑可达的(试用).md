# G.CTL.02 所有的代码都必须是逻辑可达的(试用)

- **规则ID**：bb0fc229-db19-4363-bef9-62bc4a340193
- **更新时间**：2026-04-07 04:15:00

---

**【问题级别】**

严重

**【描述】**

在以下场景中，部分代码和代码块将永远无法执行到，这类代码虽然一时无法被执行到，但后续附近代码的修改有可能会触发到它们的执行，存在潜在风险，而且会使代码不易维护，难以读懂。因此，所有的代码都必须是逻辑可达的，并且这类逻辑不可达的代码需要删除掉。

1. 跳转语句（return, break, continue 和 raise）将会使程序执行跳出当前代码块。跳转语句所在代码块中，在它之后的代码及代码块将永远无法执行到。

2. try语句中出现不可能被except代码捕获的语句（无异常或者异常不相符), except语句中代码块将永远无法执行到。

3. if语句的条件语句永真的情况下，else语句中代码块将永远无法执行到。if语句的条件语句永假的情况下，if语句中代码块将永远无法执行到。

4. while条件语句永假的情况下，循环中代码块将永远无法执行到。

**【正确示例】**

```
##### 场景1：跳转语句之后的代码
- 修复示例：return、raise语句后没有多余语句
```python
def function_with_return_no_dead_code(a):
    i = 10
    return i + a
```
##### 场景2：异常不相符
- 修复示例：捕获代码可能会出现的异常
```python
import os


def function_with_try_no_dead_code(arg):
    try:
        int_arg = open(arg, "r")
    except FileNotFoundError as e: 
        print(arg)  # 符合
```
##### 场景3：if语句的条件语句永假
- 修复示例：if条件语句根据代码逻辑为真为假
```python
def function_with_if_no_dead_code(arg):
    if arg:  # 符合
        do_something_else(arg)
    else:
        do_something(arg)  
```
##### 场景4：while条件语句永假
- 修复示例：修改while条件语句
```python
def function_with_while_no_dead_code(arg):
    while arg > 0:  # 符合
        do_some_thing(arg)
```


```
**【错误示例】**

```
##### 场景1：跳转语句之后的代码
- 错误示例：return语句后多余的语句
```python
def function_with_return_dead_code(a):
    i = 10
    return i + a
    i += 1  # 不符合，这里的代码无法被执行到
```
##### 场景2：异常不相符
- 错误示例：捕获代码不会抛出的异常
```python
import os


def function_with_try_no_dead_code(arg):
    try:
        int_arg = os.path.join(os.path.dirname(__file__), arg)
     except FileNotFoundError as e:
        do_some_thing(arg)  # 不符合，这里的处理将永远无法被执行
```
##### 场景3：if语句的条件语句永假
- 错误示例：if语句永为假
```python
def function_with_if_no_dead_code(arg):
    if False:
        do_something_else()  # 不符合，这里的处理将永远无法被执行
    else:
        do_something()  
```
##### 场景4：while条件语句永假
- 错误示例：while条件语句永假
```python
def function_with_while_no_dead_code(arg):
    while False:
        do_some_thing(arg)  # 不符合，这里的处理将永远无法被执行
```


```
**【修复建议】**

必须保持代码逻辑可达，要么清理无法执行到的代码，要么调整代码位置，把逻辑修改正确。
