# G.CMT.01 在公开的返回Result类型返回的函数文档中增加 # Error 注释-试行

- **规则ID**：899e99a7-9ef4-47fa-b4a2-15ab4a26601c
- **更新时间**：2025-06-05 04:40:01

---

**【问题级别】**

提示

**【描述】**

在公开（pub）的返回Result类型函数文档中，建议增加 # Error 注释来解释该函数返回的错误类型，方便用户处理错误。

说明： 该规则通过 cargo clippy 来检测。默认不会警告。

**【正确示例】**

```
# use std::io;
/// # Errors
///
/// Will return `Err` if `filename` does not exist or the user does not have
/// permission to read it.
pub fn read(filename: String) -> io::Result<String> {
    unimplemented!();
}

```
**【错误示例】**

```
# use std::io;
pub fn read(filename: String) -> io::Result<String> {
    unimplemented!();
}

```
**【修复建议】**
