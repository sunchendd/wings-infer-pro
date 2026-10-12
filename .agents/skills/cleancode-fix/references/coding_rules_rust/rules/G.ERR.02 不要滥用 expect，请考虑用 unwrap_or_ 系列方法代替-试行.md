# G.ERR.02 不要滥用 expect，请考虑用 unwrap_or_ 系列方法代替-试行

- **规则ID**：cc909b57-046d-4fe5-a779-9a0397cf0a71
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

一般

**【描述】**

使用 expect 的时候请遵循 expect 的语义，不要滥用。参考 ： P.ERR.05 。



但是对于一些存在“副作用”的函数，在 遇到 None 或 Err 时，可能需要返回一些指定的值。这个时候用 expect 就不太符合语义。



如果你的用法完全符合 expect 语义，那么可以设置 #![allow(clippy::expect_fun_call]

**【正确示例】**

```
let foo = Some(String::new());
let err_code = "418";
let err_msg = "I'm a teapot";
foo.unwrap_or_else(|| panic!("Err {}: {}", err_code, err_msg));  // 你可以根据场景选择性使用 panic! 或者 不 panic!

```
**【错误示例】**

```
let foo = Some(String::new());
let err_code = "418";
let err_msg = "I'm a teapot";
foo.expect(&format!("Err {}: {}", err_code, err_msg)); 
// or
foo.expect(format!("Err {}: {}", err_code, err_msg).as_str());

```
**【修复建议】**
