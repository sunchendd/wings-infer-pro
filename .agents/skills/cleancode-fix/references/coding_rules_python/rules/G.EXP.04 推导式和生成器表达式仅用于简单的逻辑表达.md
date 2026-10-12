# G.EXP.04 推导式和生成器表达式仅用于简单的逻辑表达

- **规则ID**：b7fad3ad-481c-4bdd-8e8b-d00558afb371
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

复杂的推导式和生成器表达式，会伤害代码的易读性，难于阅读，难于理解，难于维护，且不易调试。

如果表达式比较简单可以一行书写，如果表达式比较复杂，需要将每个子句单独书写一行，分行书写，

而且按照格式对齐。

**【正确示例】**

```
##### 场景1：推导式和生成器表达式的使用
- 修复示例：简单易懂的推导表达式
```python
# 符合
result = [{'key': value} for value in range(10000) if is_odd(value)]

# 符合
result = [{'key': key, 'value': value}
          for key, value in generate_iterable(some_input)
          if predicate(key, value)]

return {key: value
        for x in generate_iterable(parameter)
        if predicate(key, value)}

squares_generator = (x**2 for x in range(10))

unique_names = {user.name for user in users if user}
```
##### 场景2：比较复杂的推导表达式的书写方式
- 修复示例：有多个子句的推导表达式单独成一行
 ```python
# 符合，多个子句单独写一行，分行书写，格式对齐
split_theme_list_list = [
     theme_read[i * theme_split_len:(i + 1) * theme_split_len] 
     for i in range(theme_split_num - 1)
]
```

```
**【错误示例】**

```
##### 场景1：推导式和生成器表达式的使用
- 错误示例：有多个子句，多重循环的推导表达式
```python
# 不符合，多个子句的推导表达式
result = [
(x, y) for x in range(10) for y in range(5) if x * y > 10]

# 不符合，多个循环的推导表达式
return ((x, y, z)
        for x in range(5)
        for y in range(5)
        if x != y
        for z in range(5)
        if y != z)
```
##### 场景2：比较复杂的推导表达式的书写方式
- 错误示例：有多个子句的推导表达式合成一行
 ```python
# 不符合，多个子句的推导表达式合成一行书写
split_theme_list_list = [theme_read[i * theme_split_len:(i + 1) * theme_split_len] for i in
                             range(theme_split_num - 1)]
```

```
**【修复建议】**

慎用复杂的推导式和生成器表达式，可以拆分成多个简单的推导式和生成器表达式。将复杂的推导表达式每个子句分行书写，

单独成一行，格式对齐。
