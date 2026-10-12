# G.CTL.04 建议使用 for x in iterable 的方式循环处理可迭代对象

- **规则ID**：b04c9de4-c9ed-4fca-a4d9-9290bee7039e
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

使用`for i in range(x):`语句，然后在循环体内对序列用下标[i]获取元素是一种较为传统的编程习惯，它有很多缺点：容易越界；在循环体内修改i容易出错；可读性差。因此，建议尽量使用`for x in iterable:`的方式，直接取序列中的每一个对象进行处理。

**【正确示例】**

```
##### 场景1：遍历列表
- 修复示例1：使用 for x in iterable 的方式直接循环遍历列表
```python
for x in my_list:  # 符合，使用迭代器直接循环遍历列表
    do_something(x)
```
- 修复示例2：有些场合下，需要在处理时使用每个元素的序号，这时可以使用`enumerate`内置函数来给元素加上序号形成元组：
```python
my_list = ['a', 'b', 'c'] 

for i, x in enumerate(my_list):  # 符合
    print(i, x)
```

```
**【错误示例】**

```
##### 场景1：遍历列表
- 错误示例：通过遍历列表长度来遍历列表
```python
for i in range(len(my_list)):  # 不符合，遍历列表使用长度遍历
    do_something(my_list[i])
```

```
**【修复建议】**

1. 使用 for x in iterable 的方式循环处理可迭代对象。

2. 有些场合下，需要在处理时使用每个元素的序号，这时可以使用`enumerate`内置函数来给元素加上序号形成元组。
