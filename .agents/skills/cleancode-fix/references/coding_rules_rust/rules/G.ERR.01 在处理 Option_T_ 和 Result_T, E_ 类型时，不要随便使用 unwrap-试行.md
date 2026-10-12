# G.ERR.01 在处理 Option<T> 和 Result<T, E> 类型时，不要随便使用 unwrap-试行

- **规则ID**：21ae6681-1263-42a8-9088-c2cc97e71668
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

当 Option<T> 和 Result<T, E>类型的值分别是 None 或 Err 时，直接对其 unwrap() 会导致程序 Panic！

**【正确示例】**

```
fn select(opt: Option<String>) {
    opt.expect("more helpful message");  // 可以用 expect 方法来处理 None 的情况
}
// OR
fn select(opt: Result<String, ()>) {
    res.expect("more helpful message");  // 可以用 expect 方法来处理 Err 的情况
}

```
**【错误示例】**

```
fn select(opt: Option<String>) {
    opt.unwrap();  // 可以用 expect 方法来处理 None 的情况
}
// OR
fn select(opt: Result<String, ()>) {
    res.unwrap();  // 可以用 expect 方法来处理 Err 的情况
}

```
**【修复建议】**
