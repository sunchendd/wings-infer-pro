# G.CNS.05 对于适用 const fn 的函数或方法宜尽可能地使用 const fn-试行

- **规则ID**：00ea024f-8ec4-499c-b8c3-7298a052f923
- **更新时间**：2025-06-05 04:40:01

---

**【问题级别】**

提示

**【描述】**

函数或方法缺失const关键词时无法被指派给常量。

但是要注意不是所有函数都能使用const fn，因为相比一般函数或方法，const fn在使用时会有限制，一些功能将无法在const fn内使用，例如迭代器。

**【正确示例】**

```
const fn foo() -> usize {
    10
}
let bar: usize = foo():   // OK
const BAZ: usize = foo(); // OK

```
**【错误示例】**

```
fn foo() -> usize {
    10
}
let bar: usize = foo();   // OK
const BAZ: usize = foo(); // ERROR

```
**【修复建议】**
