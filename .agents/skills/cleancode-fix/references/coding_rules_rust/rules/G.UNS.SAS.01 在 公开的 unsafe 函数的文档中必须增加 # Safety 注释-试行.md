# G.UNS.SAS.01 在 公开的 unsafe 函数的文档中必须增加 # Safety 注释-试行

- **规则ID**：675a8738-bca7-4023-a1ac-d2f5645c70b8
- **更新时间**：2025-06-05 04:40:04

---

**【问题级别】**

提示

**【描述】**

在公开（pub）的 unsafe 函数文档中，必须增加 # Safety 注释来解释该函数的安全边界，这样使用该函数的用户才可以安全地使用它。



说明： 该规则通过 cargo clippy 来检测。默认会发出警告。

**【正确示例】**

```
/// Creates a `Vec<T>` directly from the raw components of another vector.
    ///
    /// # Safety
    ///
    /// This is highly unsafe, due to the number of invariants that aren't
    /// checked:
    ///
    /// * `ptr` needs to have been previously allocated via [`String`]/`Vec<T>`
    ///   (at least, it's highly likely to be incorrect if it wasn't).
    /// * `T` needs to have the same size and alignment as what `ptr` was allocated with.
    ///   (`T` having a less strict alignment is not sufficient, the alignment really
    ///   needs to be equal to satisfy the [`dealloc`] requirement that memory must be
    ///   allocated and deallocated with the same layout.)
    /// * `length` needs to be less than or equal to `capacity`.
    /// * `capacity` needs to be the capacity that the pointer was allocated with.
    pub unsafe fn from_raw_parts(ptr: *mut T, length: usize, capacity: usize) -> Self {
        unsafe { Self::from_raw_parts_in(ptr, length, capacity, Global) }
    }

```
**【错误示例】**

```
/// Creates a `Vec<T>` directly from the raw components of another vector.
    pub unsafe fn from_raw_parts(ptr: *mut T, length: usize, capacity: usize) -> Self {
        unsafe { Self::from_raw_parts_in(ptr, length, capacity, Global) }
    }

```
**【修复建议】**
