# G.FUD.02 当函数参数实现了 Copy，并且是按值传入，如果值可能会太大，则宜考虑按引用传递-试行

- **规则ID**：9541152f-f06c-4210-9f44-f17fa0857fed
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

通过值传递的参数可能会导致不必要的 memcpy 拷贝，这可能会造成性能损失。

**【正确示例】**

```
#[derive(Clone, Copy)]
struct TooLarge([u8; 2048]);
// Good
fn foo(v: &TooLarge) {}

```
**【错误示例】**

```
#[derive(Clone, Copy)]
struct TooLarge([u8; 2048]);
// Bad
fn foo(v: TooLarge) {}

```
**【修复建议】**
