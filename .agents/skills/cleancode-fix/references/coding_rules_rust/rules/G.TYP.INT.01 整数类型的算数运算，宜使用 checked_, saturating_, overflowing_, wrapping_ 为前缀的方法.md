# G.TYP.INT.01 整数类型的算数运算，宜使用 checked_, saturating_, overflowing_, wrapping_ 为前缀的方法

- **规则ID**：1d4e2aec-41f1-4c90-87bc-a3741c0b0105
- **更新时间**：2026-04-07 04:40:00

---

**【问题级别】**

提示

**【描述】**

使用整数计算时需结合场景和业务考虑，如发生溢出、回绕或截断时，是否会产生未定义行为或不符合预期的结果，比如在计算时间或数组索引时发生整数溢出会导致错误结果或 Panic。

**【正确示例】**

```
```
let mut x: u8 = 255;
x = x.wrapping_add(1);
// Or
x = x.saturating_add(1);
```

```
**【错误示例】**

```
```
let mut x: u8 = 255;
x += 1;
```

```
**【修复建议】**

在 Rust 标准库中，提供 `add` / `checked_add` / ` saturating_add` / `overflowing_add` / `wrapping_add` 等系列方法，可结合场合选择合适的方法：



- `checked_*` 系列函数返回 `Option`，一旦发生溢出则返回 None。

- `saturating_*` 系列函数返回类型是整数，如果溢出，则给出该类型可表示范围的“最大/最小”值。

- `wrapping_*` 系列函数则是直接抛弃已经溢出的最高位，将剩下的部分返回。即返回二进制补码结果。

- `overflowing_*` 系列函数返回二进制补码结果以及指示是否发生溢出的布尔值。
