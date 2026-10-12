# G.TYP.FLT.04 宜使用Rust内置方法处理浮点数计算-试行

- **规则ID**：5a7eab4b-158d-493d-ae1e-db5c3cd17bf9
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

提示

**【描述】**

内置方法会牺牲一定性能，但可以提升准确性。

**【正确示例】**

```
let a = 3f32;
let _ = a.cbrt();
let _ = a.ln_1p();
let _ = a.exp_m1();
use std::f32::consts::E;
let a = 3f32;
let _ = a.exp2();
let _ = a.exp();
let _ = a.sqrt();
let _ = a.log2();
let _ = a.log10();
let _ = a.ln();
let _ = a.powi(2);
let _ = a.mul_add(2.0, 4.0);
let _ = a.abs();
let _ = -a.abs();

```
**【错误示例】**

```
let a = 3f32;
let _ = a.powf(1.0 / 3.0);
let _ = (1.0 + a).ln();
let _ = a.exp() - 1.0;
use std::f32::consts::E;
let a = 3f32;
let _ = (2f32).powf(a);
let _ = E.powf(a);
let _ = a.powf(1.0 / 2.0);
let _ = a.log(2.0);
let _ = a.log(10.0);
let _ = a.log(E);
let _ = a.powf(2.0);
let _ = a * 2.0 + 4.0;
let _ = if a < 0.0 {
    -a
} else {
    a
};
let _ = if a < 0.0 {
    a
} else {
    -a
};

```
**【修复建议】**
