# G.TYP.09 建议优先使用语义更明确的内置函数来判断对象的类型或行为

- **规则ID**：1829c93c-da87-47f0-9f4e-53884d0aa315
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

不建议使用hasattr函数来判断对象的类型或行为，推荐使用callable()、isinstance()等对应的函数来判断对象的类型或行为；对应的函数可以更好地覆盖各种场景，并且不会随着语言的演进而失效。

**【正确示例】**

```
```
callable(obj)  # 判断是否是callable

isinstance(obj, Collections.abc.Container)  # 判断是否是容器

isinstance(obj, Collections.abc.Iterable)  # 判断是否可迭代，因为历史原因，无法判断仅实现了__getitem__的可迭代对象
```

```
**【错误示例】**

```
```
hasattr(obj, '__call__')  # 判断是否是callable

hasattr(obj, '__contains__')  # 判断是否是容器

hasattr(obj, '__iter__')  # 判断是否可迭代
```

```
**【修复建议】**

推荐使用callable()、isinstance()等对应的函数来判断对象的类型或行为
