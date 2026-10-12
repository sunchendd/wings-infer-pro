# DC.G.VAR.01 全局变量必须是只读的

- **规则ID**：117dd6a5-680e-4136-95eb-81ad2ff38c32
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：全局变量xxx必须是只读的. 定义在文件 “xxx” 的第xx行、第xx列

**【正确示例】**

```
```
var = "var"
function func()
    local varInFunc = var
    varInFunc = "modify"
    ...
end
```

```
**【错误示例】**

```
```
var = "var"
function func()
    var = "modify"
    ...
end
```

```
**【修复建议】**

此处全局的变量指没有local修饰的变量，不管是跨模块的，还是本模块的，都不可以修改
