# G.FMT.04-05 行末关键字操作符检查

- **规则ID**：7af8f17c-785e-4d6a-9539-f2a8c51157ac
- **更新时间**：2026-04-07 04:45:00

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：关键字或操作符出现在行末

**【正确示例】**

```
```
local function func(var1, var2)
    ...
end
```

```
**【错误示例】**

```
```
local function
func(var1, var2)
    ...
end
```

```
**【修复建议】**

行不要以关键字local function if elseif while until for not #结尾
