# G.TRA.BLN.09 一般情况下不要给 Copy 类型手工实现 Clone-试行

- **规则ID**：4e3f8c73-7174-4e65-bae2-bc0e149f38e1
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

手工为 Copy 类型实现 Clone ，并不能改变 Copy 类型的行为。除非你显式地去调用 clone()方法。

**【正确示例】**

```
#[derive(Copy, Clone)]
struct Foo;

```
**【错误示例】**

```
#[derive(Copy)]
struct Foo;
impl Clone for Foo {
    // ..
}

```
**【修复建议】**
