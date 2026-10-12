# G.TYP.FLT.03  对精度高要求的场景下，不应直接使用浮点数进行运算和比较-试行

- **规则ID**：b34abf2a-ab37-4cdc-b182-2aeac973dc60
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

提示

**【描述】**

浮点数计算通常都是不精确的，直接对浮点数进行运算和比较可能造成数据错误。 如何更好地处理浮点数，可以参阅 浮点数指南 。



但是对精度要求不高的场合，比如机器学习中某些场景，对此不作要求。

**【正确示例】**

```
let x = 1.2331f64;
let y = 1.2332f64;
let error_margin = f64::EPSILON; // Use an epsilon for comparison
// Or, if Rust <= 1.42, use `std::f64::EPSILON` constant instead.
// let error_margin = std::f64::EPSILON;
if (y - 1.23f64).abs() < error_margin { }
if (y - x).abs() > error_margin { }
// or
pub fn is_roughly_equal(a: f32, b: f32) -> bool {
    (a - b).abs() < f32::EPSILON
}

```
**【错误示例】**

```
let x = 1.2331f64;
let y = 1.2332f64;
if y == 1.23f64 { }
if y != x {} // where both are floats
// or
pub fn is_roughly_equal(a: f32, b: f32) -> bool {
    (a - b) < f32::EPSILON
}

```
**【修复建议】**
