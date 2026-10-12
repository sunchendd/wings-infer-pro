# G.SAF.FFI.05 extern 外部函数应显式指定 ABI 标识

- **规则ID**：6b6ca0a8-1d69-4fda-968c-5b7157658f0b
- **更新时间**：2026-04-07 04:40:00

---

**【问题级别】**

一般

**【描述】**

extern 外部函数应显式指定 ABI 标识

**【正确示例】**

```
```
extern "C" {
   fn c_function();
}
```

```
**【错误示例】**

```
```
extern {
    fn c_function();
}
```

```
**【修复建议】**

extern 外部函数应显式指定 ABI 标识
