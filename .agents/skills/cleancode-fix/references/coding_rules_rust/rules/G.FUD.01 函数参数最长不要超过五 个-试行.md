# G.FUD.01 函数参数最长不要超过五 个-试行

- **规则ID**：1fe986ea-d31e-4dce-ae58-d985fba3d97c
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

一般

**【描述】**

为了提升代码可读性，函数的参数最长不宜超过五个。

**【正确示例】**

```
struct Color;
// 此处使用常量泛型（const generic） 来接收后面多个 u32 类型的参数
// 使用元组缩短 2~3 个参数为一个参数
fn foo<T, const N: usize>(x: (f32, f32), name: &str, c: Color, last: [T; N]) {
    ;
}
fn main(){
    let arr = [1u32, 2u32];
    foo((1.0f32, 2.0f32), "hello", Color, arr);
    let arr = [1.0f32, 2.0f32, 3.0f32];
    foo((1.0f32, 2.0f32), "hello", Color, arr);
}

```
**【错误示例】**

```
struct Color;
fn foo(x: f32, y: f32, name: &str, c: Color, w: u32, h: u32, a: u32, b: u32) {
    // ..
}

```
**【修复建议】**
