# G.GEN.01 不要在泛型位置上使用内建类型-试行

- **规则ID**：8ef415d8-3676-4b30-97a1-34bd2f0ac84b
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

一般

**【描述】**

这样做虽然会导致编译错误，但是这种错误会使开发者感到困惑，反而无法找到问题所在。

**【正确示例】**

```
impl<T> Foo<T> {
    fn impl_func(&self) -> T {
        42
    }
}

```
**【错误示例】**

```
impl<u32> Foo<u32> {
    fn impl_func(&self) -> u32 {
        42
    }
}
// 下面这个错误信息完全让开发者无法定位错误
// error[E0308]: mismatched types
//  --> src/lib.rs:3:9
//   |
// 1 | impl<u32> Foo<u32> {
//   |      --- this type parameter
// 2 |     fn impl_func(&self) -> u32 {
//   |                            --- expected `u32` because of return type
// 3 |         42
//   |         ^^ expected type parameter `u32`, found integer
//   |
//  = note: expected type parameter `u32`
//                       found type `{integer}`

```
**【修复建议】**
