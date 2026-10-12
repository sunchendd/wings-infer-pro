# G.ERR.01 应正确处理返回类型 Option 和 Result

- **规则ID**：056e54b0-9cd6-4c3c-9c52-166a6288dbd5
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

提示

**【描述】**

当 Option<T> 和 Result<T, E>类型的值分别是 None 或 Err 时，直接对其 unwrap() 会导致程序 Panic！

**【正确示例】**

```
```
fn select(opt: Option<String>) {
    opt.expect("more helpful message");  // 可以用 expect 方法来处理 None 的情况
}
// OR
fn select(opt: Result<String, ()>) {
    res.expect("more helpful message");  // 可以用 expect 方法来处理 Err 的情况
}
```

```
**【错误示例】**

```
```
fn select(opt: Option<String>) {
    opt.unwrap();  // 可以用 expect 方法来处理 None 的情况
}
// OR
fn select(opt: Result<String, ()>) {
    res.unwrap();  // 可以用 expect 方法来处理 Err 的情况
}
```

```
**【修复建议】**

对于返回类型为 `Option` 或 `Result` 的函数，应使用不会导致 panic 的方法显示处理返回的 `None` / `Err` 错误值。



处理方法包括：



- 使用 `match` 语句

- 使用 `unwrap_or` / `unwrap_or_else` / `unwrap_or_default` 等函数



例外：如下两种场景可直接调用 `unwrap` / `expect`：



- 调用返回 `Option` / `Result` 函数之前通过输入参数的提前校验，可以保证返回值一定不会是 `None` / `Err`。

- 业务模块的设计要求对于返回 `None` / `Err` 的情况 panic，依赖更高层的可靠性机制检测故障并实现故障恢复。
