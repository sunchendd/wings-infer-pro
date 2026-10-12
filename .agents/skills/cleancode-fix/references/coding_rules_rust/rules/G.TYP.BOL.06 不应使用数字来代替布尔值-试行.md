# G.TYP.BOL.06 不应使用数字来代替布尔值-试行

- **规则ID**：daf7e3e6-4a5f-4f78-881a-d22b34a9cb14
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

提示

**【描述】**

Rust 中布尔值就是 true 和 false。 不要试图使用数字 1 和 0 来代替布尔值。



虽然 布尔值 可以强转为 对应的数字，但是反之则不行。



不要通过判断数字来代替 布尔值，除非是 FFi 场景通过 C-ABI 和其他语言打交道。

**【正确示例】**

```
let a = true;
let b = false;
assert_eq!(1, a as u32);
assert_eq!(0, b as u32);

```
**【错误示例】**

```
let a = 1;
let b = 0;
assert_eq!(true, a == 1);  
assert_eq!(false, b == 0);

```
**【修复建议】**
