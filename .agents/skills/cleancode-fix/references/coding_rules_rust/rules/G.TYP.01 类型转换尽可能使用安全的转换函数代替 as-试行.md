# G.TYP.01 类型转换尽可能使用安全的转换函数代替 as-试行

- **规则ID**：8d2262f1-3b5e-44a4-8d9a-f370e8c2c214
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

提示

**【描述】**

Rust 的 as 转换包含了「静默的有损转换(lossy conversion)」。诸如 i32::from 之类的转换函数只会执行无损转换(lossless conversion)。 如果输入表达式的类型发生变化，使用转换函数可以防止转换变成无声的有损转换，并使阅读代码的人更容易知道转换是无损的。

**【正确示例】**

```
fn as_u64(x: u8) -> u64 {
    u64::from(x)
}
// or
f(a.try_into()?);
// or
f(a.try_into().expect("Unexpected u16 overflow in f"));
// or
let ptr: *const u32 = &42_u32;
let mut_ptr: *mut u32 = &mut 42_u32;
let _ = ptr.cast::<i32>();
let _ = mut_ptr.cast::<i32>();

```
**【错误示例】**

```
fn as_u64(x: u8) -> u64 {
    x as u64
}
// or
let a: u32;
f(a as u16);
// or
let ptr: *const u32 = &42_u32;
let mut_ptr: *mut u32 = &mut 42_u32;
let _ = ptr as *const i32;
let _ = mut_ptr as *mut i32;

```
**【修复建议】**
