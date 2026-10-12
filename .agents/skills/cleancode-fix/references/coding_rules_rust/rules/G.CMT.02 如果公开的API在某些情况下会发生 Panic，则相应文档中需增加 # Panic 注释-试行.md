# G.CMT.02 如果公开的API在某些情况下会发生 Panic，则相应文档中需增加 # Panic 注释-试行

- **规则ID**：7a587c57-3d08-49be-8a72-3d7fffa55660
- **更新时间**：2025-06-05 04:40:01

---

**【问题级别】**

提示

**【描述】**

在公开（pub）函数文档中，建议增加 # Panic 注释来解释该函数在什么条件下会 Panic，便于使用者进行预处理。



说明： 该规则通过 cargo clippy 来检测。默认不会警告。

**【正确示例】**

```
/// # Panics
///
/// Will panic if y is 0
pub fn divide_by(x: i32, y: i32) -> i32 {
    if y == 0 {
        panic!("Cannot divide by 0")
    } else {
        x / y
    }
}

```
**【错误示例】**

```
pub fn divide_by(x: i32, y: i32) -> i32 {
    if y == 0 {
        panic!("Cannot divide by 0")
    } else {
        x / y
    }
}

```
**【修复建议】**
