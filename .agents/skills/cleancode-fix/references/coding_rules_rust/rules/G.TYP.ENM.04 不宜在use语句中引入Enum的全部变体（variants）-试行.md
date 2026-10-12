# G.TYP.ENM.04 不宜在use语句中引入Enum的全部变体（variants）-试行

- **规则ID**：9af26102-c7ae-44a5-9767-8cda62b0bf68
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

提示

**【描述】**

使用 Enum 的类型前缀可以使代码更加可读。

**【正确示例】**

```
use std::cmp::Ordering;
foo(Ordering::Less)

```
**【错误示例】**

```
use std::cmp::Ordering::*; // 这里导入了全部变体
foo(Less);

```
**【修复建议】**
