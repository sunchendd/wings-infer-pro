# G.SAF.FFI.01 FFI 边界应确保字符串参数正确传递和使用

- **规则ID**：60ed59e4-1b07-4ed6-a89d-52175ff6173d
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

一般

**【描述】**

FFI 边界应确保字符串参数正确传递和使用

**【正确示例】**

```
```
extern "C" {
    fn greet(name: *const c_char);
}
let name = std::ffi::CString::new("Rust");
unsafe {
    greet(name.as_ptr() as *const _);
}
```

```
**【错误示例】**

```
```
extern "C" {
    fn greet(name: *const c_char);
}
let name = String::from("Rust");
unsafe {
    greet(name.as_ptr() as *const _);
}
```

```
**【修复建议】**

Rust标准库提供了两种与 C 语言字符串兼容的字符串类型：CString 和 CStr。从 Rust 向 C 函数传递字符串时应当向将字符串转换为 CString 类型，再用 .as_ptr() 方法获取 C 字符串指针。而在 Rust 中读取 C 函数返回的字符串指针，应该通过 CStr::from_ptr() 函数将其转换为 CStr 类型再读取。
