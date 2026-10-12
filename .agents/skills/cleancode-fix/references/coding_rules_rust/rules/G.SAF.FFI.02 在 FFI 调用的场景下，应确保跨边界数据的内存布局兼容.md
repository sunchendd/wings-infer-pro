# G.SAF.FFI.02 在 FFI 调用的场景下，应确保跨边界数据的内存布局兼容

- **规则ID**：7b7f76cd-445c-44b9-937d-a2f59f92544b
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

一般

**【描述】**

在 FFI 调用的场景下，应确保跨边界数据的内存布局兼容

**【正确示例】**

```
```
#[repr(C)]
struct Foo3 {
    a: libc::c_char,
    b: libc::c_int,
    c: libc::c_longlong,
}
extern "C" fn c_abi_fn4(arg_one: u32, arg_two: *const Foo3) {}
```

```
**【错误示例】**

```
```
struct Foo3 {
    a: libc::c_char,
    b: libc::c_int,
    c: libc::c_longlong,
}
extern "C" fn c_abi_fn4(arg_one: u32, arg_two: *const Foo3) {}
```

```
**【修复建议】**

FFI 函数传递的任何数据类型，需要保证内存布局一致。对于结构体、枚举和联合体，应该通过添加 #[repr(C)] 属性，来避免字段顺序重排，以保证内存布局的兼容。
