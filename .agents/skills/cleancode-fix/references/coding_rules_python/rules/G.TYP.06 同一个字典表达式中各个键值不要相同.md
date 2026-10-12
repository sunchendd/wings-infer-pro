# G.TYP.06 同一个字典表达式中各个键值不要相同

- **规则ID**：d5923d46-91ef-4834-891d-57453d6e6ccd
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

同一个字典表达式中的各个键值不要重复，如果存在重复的键值，后面的键值对会覆盖前面的键值对，会导致程序出现意想不到的结果。

**【正确示例】**

```
##### 场景1：字典初始化键值
- 修复示例：字典的键值各不相同

```python

dict_duplicate_values = {"lilei": 20, "hanmeimei": 30, "wangqiang": 45}    # 符合，键值没有重复的

print(dict_duplicate_values)  # {'lilei': 20, 'hanmeimei': 30, 'wangqiang': 45}

```

```
**【错误示例】**

```
##### 场景1：字典初始化键值
- 错误示例：字典变量包含相同的键值，并且对应的值不相同
```python
dict_duplicate_values = {"lilei": 20, "hanmeimei": 30, "wangqiang": 45, "lilei": 23}    # 不符合，键值有2个`lilei`
print(dict_duplicate_values)  # {'lilei': 23, 'hanmeimei': 30, 'wangqiang': 45}
```

```
**【修复建议】**

字典表达式不能包含相同的键值。
