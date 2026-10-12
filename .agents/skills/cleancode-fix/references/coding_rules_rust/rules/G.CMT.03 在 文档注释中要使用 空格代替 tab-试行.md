# G.CMT.03 在 文档注释中要使用 空格代替 tab-试行

- **规则ID**：42185319-87f3-4946-a79e-b72680882896
- **更新时间**：2025-06-05 04:40:01

---

**【问题级别】**

一般

**【描述】**

Rust 代码风格中提倡使用空格代替tab，在文档注释中也应该统一使用空格。

**【正确示例】**

```
///
/// Struct to hold two strings:
///     - first        one
///     - second    one
pub struct DoubleString {
   ///
   ///     - First String:
   ///         - needs to be inside here
   first_string: String,
   ///
   ///     - Second String:
   ///         - needs to be inside here
   second_string: String,
}

```
**【错误示例】**

```
///
/// Struct to hold two strings:
/// 	- first		one
/// 	- second	one
pub struct DoubleString {
   ///
   /// 	- First String:
   /// 		- needs to be inside here
   first_string: String,
   ///
   /// 	- Second String:
   /// 		- needs to be inside here
   second_string: String,
}

```
**【修复建议】**
