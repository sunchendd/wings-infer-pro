# G.STR.02 在追加字符串时使用push_str方法可读性更强-试行

- **规则ID**：8b10ad13-510f-426c-a357-4aa54db35434
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

与+=相比，可读性更好。

**【正确示例】**

```
let mut x = "Hello".to_owned();
// More readable
x += ", World";
x.push_str(", World");

```
**【错误示例】**

```
let mut x = "Hello".to_owned();
x = x + ", World";

```
**【修复建议】**
