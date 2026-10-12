# DC.G.MOD.05 检查变量/函数是否在间接require的文件中定义

- **规则ID**：93dcee92-564e-4774-8924-57cbd0c3f5a4
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：变量/函数：“xxx”是在间接require的文件：“xxx”中定义的，请直接require该文件

**【正确示例】**

```
```
file ModuleA.lua
module("ModuleA", package.seeall)
require("ModuleB")

ret, val = ModuleB.foo() -- 调用ModuleB中定义的foo函数
```

```
**【错误示例】**

```
```
file ModuleC.lua
module("ModuleC", package.seeall)
require("ModuleB")

file ModuleA.lua
module("ModuleA", package.seeall)
require("ModuleC")
ret, val = ModuleB.foo() -- 调用ModuleB中定义的foo函数，ModuleB在ModuleC中间接依赖。
```

```
**【修复建议】**

使用模块的方法必须直接require该模块，而不应通过第三方模块间接require该模块
