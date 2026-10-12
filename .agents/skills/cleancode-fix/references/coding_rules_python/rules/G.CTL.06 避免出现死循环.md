# G.CTL.06 避免出现死循环

- **规则ID**：270d6d66-401a-47d8-b476-019a95b789a0
- **更新时间**：2026-04-07 04:15:00

---

**【问题级别】**

一般

**【描述】**

死循环会导致程序卡死，建议不要使用存在"死循环"风险的迭代或循环。

包括但不限于以下情况：

- 存在循环变量不被修改的情况或修改循环变量的路径不可达。

- 无退出条件的循环。

**【正确示例】**

```
##### 场景1：循环变量的路径不可达
- 修复示例：保证循环变量的路径总是可达
```python
condition = 0

while condition < 5:
    ...
    condition += 1  # 符合
```
##### 场景2：循环变量不被修改
- 修复示例：保证循环变量可以被修改
```python
condition = 0
count = 0

while condition < 5:
    ...
    count += 1  
    condition += 1  # 符合
```
##### 场景3：无退出条件的循环
- 修复示例1：采用条件退出
```python
while True:
    if timeout:  # 符合，条件退出
        break
```
- 修复示例2：采用异常退出
```python
try:
    while True:
        ...
        # raise EOFError
except EOFError as e:
    ...  # 符合，采用异常退出
```


```
**【错误示例】**

```
##### 场景1：循环变量的路径不可达
- 错误示例：
```python
condition = 0

while condition < 5:
    ...
    if False:  # 不符合，循环变量的路径不可达
        condition += 1 
```
##### 场景2：循环变量不被修改
- 错误示例：
```python
condition = 0
count = 0

while condition < 5:
    count += 1  # 不符合，循环变量不被修改
```
##### 场景3：无退出条件的循环
- 错误示例：
```python
while True:
    ...  # 不符合，无退出条件的循环
```


```
**【修复建议】**

1. 保证循环变量的路径可达并且可以被修改。

2. while条件语句永真的情况下，保证循环代码中存在退出条件。也可以使用异常退出循环。
