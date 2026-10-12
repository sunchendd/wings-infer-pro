# G.TYP.INT.01 在用整数计算的时候需要考虑整数溢出、回绕和截断的风险-试行

- **规则ID**：f62ebe78-9cc5-424b-b646-cacee7cef3dc
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

提示

**【描述】**

需要结合场景和业务来考虑如果发生溢出、回绕或截断的时候，是否会引起严重的问题。



比如，对于时间要求精准的系统，如果在计算时间发生整数溢出，或者去计算某个数组的索引等，那可能会发生严重问题。但如果你只是一个简单的计算器，不会被用到具体的业务场合，那溢出也没有关系，因为你只需要在合理的数字范围内计算性能最好。

**【正确示例】**

```
assert_eq!((-5i32).checked_abs(), Some(5));
assert_eq!(100i32.saturating_add(1), 101);
fn add_num(a: u8) -> u8 { a.wrapping_add(255) }
fn test_integer_overflow() {
    // 对于字面量或常量表达式，debug 与 release 编译模式都会有溢出检查
    let mut a: u8 = 255 + 1;
    // debug模式，运行会Panic
    // release模式，x 会等于 0
    let mut x: u8 = 255;
    x = add_num(x);
    println!("x={}", x);
}

```
**【错误示例】**

```
assert_eq!((-5i32).abs(), 5);
assert_eq!(100i32+1, 101);
fn test_integer_overflow() {
    // debug 与 release 编译都会有溢出检查
    let mut a: u8 = 255 + 1;
    
    // debug模式，运行panic；release模式，x = 0
    let mut x: u8 = 255;
    x += 1;
    println!("x={}", x);
}

```
**【修复建议】**
