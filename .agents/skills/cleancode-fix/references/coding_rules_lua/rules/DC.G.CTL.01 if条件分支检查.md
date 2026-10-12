# DC.G.CTL.01 if条件分支检查

- **规则ID**：dae91f83-6d18-445c-b876-fed6a044eac9
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：该if分支对同一变量做了4次以上判断，可以考虑采用Map方式处理

**【正确示例】**

```
```
local tbl = {A, B, C, D, E}
for _, value in ipairs(tbl) do
    if var == value then
        return OK
    end
end
```

```
**【错误示例】**

```
```
if var == A or
   var == B or
   var == C or
   var == D or
   var == E then
    return OK
end
```

```
**【修复建议】**

在 if / else if 语句中对同一个变量做4次以上的判断会导致代码冗长不利于阅读，建议优化设计予以避免
