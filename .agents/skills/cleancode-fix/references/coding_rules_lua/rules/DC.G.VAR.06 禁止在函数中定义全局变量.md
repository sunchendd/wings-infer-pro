# DC.G.VAR.06 禁止在函数中定义全局变量

- **规则ID**：dff46268-ced0-4c83-8ae1-a1e0c8e7bbf9
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：函数“xxx”中违规定义了全局变量“xxx”，禁止在函数中定义全局变量

**【正确示例】**

```
```
local function foo(c)
    local n = 100
    if c > 0 then
        return n + 1
    end
    return 0
end
```

```
**【错误示例】**

```
```
local function foo(c)
    n = 100 
    if c > 0 then
        return n + 1
    end
    return 0
end
```

```
**【修复建议】**

禁止在函数中定义全局变量
