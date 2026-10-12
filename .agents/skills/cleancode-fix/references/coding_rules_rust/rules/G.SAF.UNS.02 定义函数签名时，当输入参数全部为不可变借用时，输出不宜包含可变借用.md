# G.SAF.UNS.02 定义函数签名时，当输入参数全部为不可变借用时，输出不宜包含可变借用

- **规则ID**：482ce7f0-ef46-48ae-a62b-343c0f5e4b63
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

提示

**【描述】**

将某个包含 Unsafe 代码的函数安全抽象为 Safe 函数的时候，要注意符合规则中描述的签名约定：不能输入一个不可变借用，返回一个可变的，这是违反 Rust 安全准则的。



在相关的需求场景下，可以使用 Safe Rust 提供的 Cell/RefCell 来实现。

**【正确示例】**

```
```
pub fn as_mut_slice(&mut self) -> &mut [T] {
    unsafe {
        slice::from_raw_parts_mut(self.ptr as *mut T, self.len())
    }
}
```

```
**【错误示例】**

```
```
pub fn as_mut_slice(&self) -> &mut [T] {
    unsafe {
        slice::from_raw_parts_mut(self.ptr as *mut T, self.len())
    }
}
```

```
**【修复建议】**

参数与返回值中其引用的可变性要一致，在相关的需求场景下，可以使用 Safe Rust 提供的 Cell/RefCell 来实现。
