# DC.G.VAR.03 检查局部变量和全局变量重名

- **规则ID**：946aa68f-7eee-4656-a072-52475f3e119d
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：局部变量“xxx”和全局变量重名，该全局变量位于文件<xxx>的第xx行、第xx列

**【正确示例】**

```
```
globalVar = "var"
local function func(var1)
    local var = var1
    ...
end
```

```
**【错误示例】**

```
```
a = 100 
local function foo(c)
    local a = c 
    if a > 0 then
        return a + 1
    end
    return 0
end
```

```
**【修复建议】**

局部变量a不要跟全局的变量a重名
