# DC.G.VAR.07 禁止持久缓存其他模块的外部可见符号

- **规则ID**：600699b8-29a2-414a-94ca-520f24cab43e
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：变量“xxx”不是在该文件中定义的，不能赋值给非局部变量（会影响打补丁的效果）

**【正确示例】**

```
```
module("a", package.seeall)
require("m")
local function foo()
    local val = m.func -- Good: 函数赋值给局部变量，不会影响模块 m 打补丁效果
    ...
end
```

```
**【错误示例】**

```
```
module("a", package.seeall)
require("m")
local val = m.func -- Bad: 函数赋值给文件内全局，会影响模块 m 打补丁效果
local function foo()
    ...
end
```

```
**【修复建议】**

m.func只能赋值给局部变量
