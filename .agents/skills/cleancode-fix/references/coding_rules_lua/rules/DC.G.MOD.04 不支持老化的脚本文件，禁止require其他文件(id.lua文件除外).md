# DC.G.MOD.04 不支持老化的脚本文件，禁止require其他文件(id.lua文件除外)

- **规则ID**：2683d990-5201-4de0-a9b1-c01efb1ffaee
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：文件“xxx”属于不支持老化的脚本文件，禁止require其他文件(id.lua文件除外

**【正确示例】**

```
```
module("ModuleA", package.seeall) -- ModuleA支持老化
require("ModuleB") -- ModuleB不支持老化
require("ModuleC") -- ModuleC支持老化
```

```
**【错误示例】**

```
```
module("ModuleA", package.seeall) -- ModuleA不支持老化
UNAGING = true -- 数通通过设置module表中的UNAGING字段为true标识该文件不老化
require("ModuleC") -- ModuleC支持老化，但由于被不支持老化的ModuleA依赖，也不能老化。
```

```
**【修复建议】**

被不支持老化的文件require的文件也会常驻内存，这将产生不合理的文件驻留，导致不必要的内存资源占用。
