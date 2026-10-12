# G.NAM.02-02 文件对外导出接口(非local)，是否重复文件名或module名检查

- **规则ID**：23c9748e-437b-4acb-8b99-0a44de93254c
- **更新时间**：2026-04-07 04:45:00

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：文件对外导出接口“xxx”的命名与其module名或文件名重复，文件名为xxx，module名为xxx

**【正确示例】**

```
```
complex.lua
function add(...) ... End
```

```
**【错误示例】**

```
```
complex.lua
function complex_add(...) ... End
```

```
**【修复建议】**

对外函数，前缀冗余！命名成 add 即可
