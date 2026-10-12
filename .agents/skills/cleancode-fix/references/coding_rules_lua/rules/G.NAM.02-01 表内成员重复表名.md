# G.NAM.02-01 表内成员重复表名

- **规则ID**：ec027d57-230d-4ea9-8b76-277b147c6f45
- **更新时间**：2026-04-07 04:45:00

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：表内部变量“xxx”重复表名

**【正确示例】**

```
```
local complex_oper = {
    add = function(...) ... end 
    sub = function(...) ... end
}
```

```
**【错误示例】**

```
```
local complex_oper = {
    complex_add = function(...) ... end 
    complex_sub = function(...) ... end 
}
```

```
**【修复建议】**

通过表访问其内部变量（包括函数）时，表信息是已知的, 不需要包含,命名应尽量简洁
