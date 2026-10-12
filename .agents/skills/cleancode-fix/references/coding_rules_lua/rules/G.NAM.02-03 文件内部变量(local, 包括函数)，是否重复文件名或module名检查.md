# G.NAM.02-03 文件内部变量(local, 包括函数)，是否重复文件名或module名检查

- **规则ID**：b0856ae2-01c1-4ad4-9db0-0d124811d787
- **更新时间**：2026-04-07 04:45:00

---

**【问题级别】**

一般

**【描述】**

行号：xxx，列号：xxx：局部变量/函数“xxx”的命名与其module名或文件名重复，文件名为xxx，module名为xxx

**【正确示例】**

```
```
complex.lua
local function add_inner(...) ... end
```

```
**【错误示例】**

```
```
complex.lua
local function complex_add_inner(...) ... End
```

```
**【修复建议】**

内部函数，外部不可见，前缀同样冗余
