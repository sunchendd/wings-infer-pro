# G.MOD.02 模块（文件）禁止引用不需要的模块

- **规则ID**：84e22999-9f86-4ae7-9316-e26db9132fb6
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：无效的require “xxx”

**【正确示例】**

```
```
-- a.lua
module("a", package.seeall)
require("b")
print(b.globalVar)
-- b.lua
module("b", package.seeall)
globalVar = "globalVar"
```

```
**【错误示例】**

```
```
-- a.lua
module("a", package.seeall)
require("b")
...
-- b.lua
module("b", package.seeall)
globalVar = "globalVar"
```

```
**【修复建议】**

引用不需要的模块，虽没有功能问题，但可能浪费系统资源
