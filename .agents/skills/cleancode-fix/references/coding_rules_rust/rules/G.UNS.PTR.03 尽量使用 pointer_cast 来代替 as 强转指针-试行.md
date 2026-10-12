# G.UNS.PTR.03 尽量使用 pointer::cast 来代替 as 强转指针-试行

- **规则ID**：75e27981-52d9-4d35-b89b-4986b75aa0c6
- **更新时间**：2025-06-05 04:40:04

---

**【问题级别】**

一般

**【描述】**

使用 pointer::cast 方法转换更加安全，它不会意外地改变指针的可变性，也不会将指针转换为其他类型。

**【正确示例】**

```
let ptr: *const u32 = &42_u32;
let mut_ptr: *mut u32 = &mut 42_u32;
let _ = ptr.cast::<i32>();
let _ = mut_ptr.cast::<i32>();

```
**【错误示例】**

```
let ptr: *const u32 = &42_u32;
let mut_ptr: *mut u32 = &mut 42_u32;
let _ = ptr as *const i32;
let _ = mut_ptr as *mut i32;

```
**【修复建议】**
