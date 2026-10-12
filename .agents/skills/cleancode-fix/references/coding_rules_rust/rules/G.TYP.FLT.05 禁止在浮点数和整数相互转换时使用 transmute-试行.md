# G.TYP.FLT.05 禁止在浮点数和整数相互转换时使用 transmute-试行

- **规则ID**：c01ab1d7-ba96-4b68-bbb4-fc61698a685b
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

一般

**【描述】**

使用transmute转换是非常容易出错的，建议使用 to_bites 这样转换更加安全。

**【正确示例】**

```
let _: f32 = f32::from_bits(1_u32);
let _: u32 = 1f32.to_bits();

```
**【错误示例】**

```
unsafe {
    let _: u32 = std::mem::transmute(1f32);
    let _: f32 = std::mem::transmute(1_u32); // where x: u32
}

```
**【修复建议】**
