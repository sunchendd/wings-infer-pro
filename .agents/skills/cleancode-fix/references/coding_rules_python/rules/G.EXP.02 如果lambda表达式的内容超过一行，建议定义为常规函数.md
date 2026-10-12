# G.EXP.02 如果lambda表达式的内容超过一行，建议定义为常规函数

- **规则ID**：71754582-9228-43ce-b1ed-b8e2e1d5f5a9
- **更新时间**：2026-04-07 04:15:00

---

**【问题级别】**

一般

**【描述】**

如果lambda表达式的内容太复杂的话，代码可读性会变差，使人难以理解，建议使用常规函数来代替。

**【正确示例】**

```
##### 场景1：单个列表处理
- 修复示例：使用函数来处理列表元素
```python
def division(x):
    if x % 5 == 0:
        return x
    elif x % 6 == 0:
        return x
    else:
        return 0


mylist = [3, 4, 36, 25, 56]
# 符合，使用函数代替lambda
mylist_division = map(division, mylist)
```
##### 场景2：多个列表处理
- 修复示例：使用标准库operator中的mul方法
```python
from operator import mul


vector_first = [1, 2, 3, 4, 5]
vector_last = [5, 4, 3, 2, 1]
# 符合
sum(map(mul, vector_first, vector_last))
```

```
**【错误示例】**

```
##### 场景1：单个列表处理
- 错误示例：对列表的元素处理，使用过于复杂的lambda表达式
```python
mylist = [3, 4, 36, 25, 56]
# 不符合，lambda表达式过于复杂
mylist_division = map(lambda x: x if x % 5 == 0 else (x if x % 6 == 0 else 0), mylist)
```
##### 场景2：多个列表处理
- 错误示例：处理2个列表的元素，使用lambda表达式
```python
vector_first = [1, 2, 3, 4, 5]
vector_last = [5, 4, 3, 2, 1]
# 不符合
sum(map(lambda x, y: x*y, vector_first, vector_last))
```

```
**【修复建议】**

建议定义为常规函数的场景如下：

1. lambda表达式的内容较长，例如超过120个字符的lambda表达式建议改为常规函数。

2. lambda表达式的结构较复杂，例如lambda parameter: exp1 if condition1 else (exp2 if condition2 else exp3)类似或更多层嵌套的lambda表达式建议改为常规函数。

3. 标准库operator中已提供的简单运算，不建议再通过重新定义lambda表达式的方法实现，建议直接使用operator中的现有方法。
