# DC.G.MOD.03 文件的第一个语句必须为module调用（模块定义）

- **规则ID**：6fb1267f-943b-4528-9fcc-f4e0a680ef10
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：文件的第一个语句必须为module调用（模块定义）

**【正确示例】**

```
```
module("a", package.seeall)
```

```
**【错误示例】**

```
```
require("b")
local v
...
module("a", package.seeall)
```

```
**【修复建议】**

如果该文件调用了module，则module函数的作用是把其后面的方法加入全局表中。当文件的第一个语句为module调用时，可以将文件所有方法纳入该module，以实现require文件后可以直接使用module名访问该文件所有函数的通常做法。
