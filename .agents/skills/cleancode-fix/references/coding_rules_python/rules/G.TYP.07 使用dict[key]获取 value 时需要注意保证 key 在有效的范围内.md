# G.TYP.07 使用dict[key]获取 value 时需要注意保证 key 在有效的范围内

- **规则ID**：12dab8df-9d6c-4866-a0ae-15d9a0e4c194
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

Python的字典dict可以使用key获取其对应的value。但是当key在dict的key值列表中不存在时，直接使用dict[key]获取value会报KeyError。从而会导致程序异常崩溃，

因此需要注意从代码层面保证 key 在有效的范围内。

**【正确示例】**

```
##### 场景1：使用KeyError捕获字典key的取值异常
- 修复示例：对key不存在的情况做异常处理
```python
example_dict = dict()
example_key = 'example_key'
try:
    example_value = example_dict[example_key]
except KeyError:
    ...  # 符合，对key不存在的情况做异常处理
```
##### 场景2：使用dict.get()的方法来代替直接取值
- 修复示例：使用dict.get()的方法，设置默认值为'Not exist'
```python
example_dict = dict()
example_key = 'example_key'
example_value = example_dict.get(example_key,  'Not exist')  # 符合，使用dict.get()的方法，设置默认值为'Not exist'

# 无论是否设置默认值，在使用的时候都应该进行判断，以保证安全性
if example_value == 'Not exist':
    pass
else:
    pass
```
##### 场景3：使用defaultdict类来代替直接取值
- 修复示例：使用defaultdict类，默认值为空字符串' '
```python
from collections import defaultdict


example_dict = defaultdict(str)  # 符合，使用defaultdict类，默认值为空字符串' '
example_key = 'example_key'
print(example_dict[example_key])
```

```
**【错误示例】**

```
##### 场景1：使用KeyError捕获字典key的取值异常
- 错误示例：没有判断key是否在字典变量中存在
```python
example_dict = dict()
example_key = 'example_key'
example_value = example_dict[example_key]   # 不符合，字典取值时没有判断键值是否存在
```
##### 场景2：使用dict.get()的方法来代替直接取值
- 错误示例：没有判断key是否在字典变量中存在
```python
example_dict = dict()
example_key = 'example_key'
example_value = example_dict[example_key]   # 不符合，字典取值时没有判断键值是否存在
```
##### 场景3：使用defaultdict类来代替直接取值
- 错误示例：没有判断key是否在字典变量中存在
```python
example_dict = dict()
example_key = 'example_key'
example_value = example_dict[example_key]   # 不符合，字典取值时没有判断键值是否存在
```

```
**【修复建议】**

1. 尽量避免直接使用dict[key]的方式从字典中获取value，如果一定要使用，需要注意对key not in dict的情况做异常处理。

2. 使用dict.get(key)方法获取value，并且在使用dict.get方法时应设置默认值并对返回值进行检查，如果不设置默认值的话则默认为None。

3. 对于性能要求不高的场景，推荐使用collections模块中defaultdict类，当取一个字典中不存在的key值时，它不会报错或者取到的值为None，而是会返回一个设定的默认值。
