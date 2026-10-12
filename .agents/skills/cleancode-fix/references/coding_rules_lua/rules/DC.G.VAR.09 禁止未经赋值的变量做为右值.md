# DC.G.VAR.09 禁止未经赋值的变量做为右值

- **规则ID**：18431ea0-abdb-4f6c-9aa0-a7d64e4924ef
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：访问了未初始化的局部变量xxx

**【正确示例】**

```
```
local function foo()
    local var = "var"
    local data = var
end
```

```
**【错误示例】**

```
```
local function foo()
    local var

    local data = var -- Bad: var未经赋值就作为赋值操作的右值

    if var ~= nil then  -- Bad: var未经赋值就作为关系运算的右值
        ...
    end

    bar(var) -- Bad: var未经赋值就作为函数实参

    return var -- Bad: var未经赋值就作为函数返回值
end
```

```
**【修复建议】**

禁止未经赋值的变量做为右值
