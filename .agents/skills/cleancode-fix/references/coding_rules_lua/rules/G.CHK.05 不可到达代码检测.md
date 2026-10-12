# G.CHK.05 不可到达代码检测

- **规则ID**：5c34b502-70d3-42c2-acd0-ae7c65a109b9
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：文件中xxx行之后为不可到达的无效代码，请删除

**【正确示例】**

```
```
local function foo(condition)
    if condition then
        return 1
    else
       return 2
    end
end
```

```
**【错误示例】**

```
```
local function foo()
    local ret = OK -- Bad: 此处代码无效
    return OK
end
```

```
**【修复建议】**

良好的代码不应包含执行无效或永远执行不到的代码，否则会导致非预期结果或维护成本增加。
