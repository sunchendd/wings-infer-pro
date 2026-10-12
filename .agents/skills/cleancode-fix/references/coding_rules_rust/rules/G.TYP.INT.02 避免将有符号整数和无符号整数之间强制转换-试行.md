# G.TYP.INT.02 避免将有符号整数和无符号整数之间强制转换-试行

- **规则ID**：5573b493-1e4b-49c6-ae0d-6cae3668e5de
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

提示

**【描述】**

当有符号整数被强制转换为无符号整数时，负值会发生回绕，变成更大的正值，这在实际应用时有可能助长缓冲区溢出风险。

**【正确示例】**

```
let y : i8 = -1;
// Error: 
// the trait `From<i8>` is not implemented for `u128`
// the trait bound `u128: From<i8>` is not satisfied
let z = u128::from(y);

```
**【错误示例】**

```
let y: i8 = -1;
y as u128; // will return 18446744073709551615

```
**【修复建议】**
