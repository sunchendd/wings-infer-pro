# G.FMT.02 行宽不超过120个字符

- **规则ID**：860f21c3-4c8f-49d2-951c-40931170a5b1
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

行宽包含代码以及注释等，行宽不宜过长，否则不利于阅读。

**【正确示例】**

```
##### 场景1：代码行长度过长
- 修复示例：函数调用长度超过120，使用`\`换行连接符换行
```python
var_sum = long_var_int_one + long_var_int_two + long_var_int_three + \
          long_var_int_four + long_var_int_five + long_var_int_six
```
- 修复示例：函数调用代码长度超过120，使用规范化的格式
```python
if __name__ == '__main__':
    # 符合，代码行过长，使用规范化格式换行写
    local_min = simulated_annealing(
        prob, 
        find_max=True, 
        max_x=100,
        min_x=5,
        max_y=5340,
        min_y=-5,
        visualization=True,
        max_z=120,
        allow_edit=False
    )
    p = Person()
```


```
**【错误示例】**

```
##### 场景1：代码行长度过长
- 错误示例：函数调用代码长度超过120
```python
var_sum = long_var_int_one + long_var_int_two + long_var_int_three + long_var_int_four + long_var_int_five + long_var_int_six
```


```
**【修复建议】**

1. 代码行长度超过120，需在合适的地方换行。一般情况可使用`\`。

2. 调用函数时，长度超过120，可以让调用的函数分成多行写，可以有效减少代码行长度。

3. 列表，字典元素过多，可以使用多行的方式分行写元素。
