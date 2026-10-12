# G.MOD.01 模块（文件）禁止循环引用

- **规则ID**：b04c0db5-f09d-4b3c-8f08-57df5a6e90ce
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

存在以下文件循环包含关系（省略了后缀名）：xxx

**【正确示例】**

```
```
-- a.lua
module("a", package.seeall)
require("c")
-- b.lua
module("b", package.seeall)
require("c")
-- c.lua
module("c", package.seeall)
```

```
**【错误示例】**

```
```
-- a.lua
module("a", package.seeall)
require("b")
-- b.lua
module("b", package.seeall)
require("a")
```

```
**【修复建议】**

模块间如发产生循环引用，请考虑重新设计代码架构
