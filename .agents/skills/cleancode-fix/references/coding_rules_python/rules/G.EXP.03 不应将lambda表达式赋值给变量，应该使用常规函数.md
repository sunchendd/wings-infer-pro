# G.EXP.03 不应将lambda表达式赋值给变量，应该使用常规函数

- **规则ID**：54d2b540-ffe1-4c20-bf1b-945039c98dfc
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

把lambda表达式赋给一个变量，lambda表达式就可以和其他常规函数一样被调用，但是通过type()查看函数的类型是`<class 'function'>`。

```python

f = lambda x: 2 * x

print(f(3))  # 6

print(type(f))  # <class 'function'>

```

lambda表达式赋值给变量，返回的错误堆栈信息中，显示也是`<lambda>`，从而会导致调试困难。

**【正确示例】**

```
##### 场景1：表达式赋值
- 修复示例：把函数赋值给变量，然后调用
```python
def exact_division(x):
    return 10 // x


func = exact_division
# 符合
print(func(0))  # 可以显示出错方法的堆栈信息
```

```
**【错误示例】**

```
##### 场景1：表达式赋值
- 错误示例：把lambda表达式赋值给变量，然后调用
```python
# 不符合
exact_division = lambda x: 10 // x
print(exact_division(0))  # 此处异常不好调试
```

```
**【修复建议】**

不要把lambda表达式赋值给变量。
