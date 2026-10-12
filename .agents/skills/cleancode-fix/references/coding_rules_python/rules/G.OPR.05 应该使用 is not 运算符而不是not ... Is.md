# G.OPR.05 应该使用 is not 运算符而不是not ... Is

- **规则ID**：d2b3f588-9d7b-4af5-b7d6-8ba006db8333
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

`x is not None`和`not x is None`虽然有相同的功能，但是前者的可读性更强，后者易产生歧义，导致代码可读性变差。

**【正确示例】**

```
##### 场景1：判断对象是否为None
- 修复示例：使用`x is not None`判断对象是否为None
```python
if foo is not None:    # 符合
    pass
```


```
**【错误示例】**

```
##### 场景1：判断对象是否为None
- 错误示例：使用`not x is None`判断对象是否为None
```python
if not foo is None:   # 不符合
    pass
```


```
**【修复建议】**

使用 is not 运算符而不是not ... is。
