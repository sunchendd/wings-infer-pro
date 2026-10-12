# G.CNS.01 常量类型不应具有内部可变性

- **规则ID**：deb51873-f2d0-4a4b-bd7e-dfa761590243
- **更新时间**：2026-04-07 04:40:00

---

**【问题级别】**

一般

**【描述】**

内部可变性类型包括：atomics, Cell, RefCell, UnsafeCell, Mutex, RwLock, OnceLock 等，对 const 变量的修改是无效的，有可能跟程序语义预期结果不符

**【正确示例】**

```


```
**【错误示例】**

```


```
**【修复建议】**

内部可变性类型包括：`atomics`, `Cell`, `RefCell`, `UnsafeCell`, `Mutex`, `RwLock`, `OnceLock` 等，对 const 变量的修改是无效的，有可能跟程序语义预期结果不符
