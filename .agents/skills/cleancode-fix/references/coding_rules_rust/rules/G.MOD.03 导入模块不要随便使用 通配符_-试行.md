# G.MOD.03 导入模块不要随便使用 通配符*-试行

- **规则ID**：08fd7af9-270e-427b-b90e-9f602db57f23
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

使用通配符导入会污染命名空间，比如导入相同命名的函数或类型。

**【正确示例】**

```
use crate1::foo; // Imports a function named foo
foo(); // Calls crate1::foo

```
**【错误示例】**

```
use crate2::*; // Has a function named foo
foo(); // Calls crate1::foo

```
**【修复建议】**
