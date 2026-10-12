# DC.G.VAR.05 检查同名局部变量定义隐藏

- **规则ID**：e86030f6-eeca-41ec-a2b6-1d7875ce123e
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：局部变量“xxx”定义隐藏了第xx行的同名符号定义

**【正确示例】**

```
```
local v
local function foo()
    local v1 = 1
    if ... then
        local v2 = 2 
        ...
    end
end
```

```
**【错误示例】**

```
```
local v = 0
local function foo()
    local v = 1 
    if ... then
        local v = 2 
        ...
    end
end
```

```
**【修复建议】**

局部变量不要与上层作用域中变量同名
