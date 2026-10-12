# DC.G.EXP.01 禁止使用{}作为比较表达式左右值

- **规则ID**：edba0f51-de80-4f73-80aa-f580234d942e
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：使用了{}作为比较表达式左右值

**【正确示例】**

```
```
if type(t) == 'table' and next(t) == nil then
    print('Empty table!')
end
```

```
**【错误示例】**

```
```
if t == {} then
    print('Empty table!')
end
```

```
**【修复建议】**

禁止使用{}作为比较表达式左右值
