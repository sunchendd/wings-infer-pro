# G.SAF.MEM.01 应校验内存申请函数的输入参数和返回值

- **规则ID**：954acfc8-6c8e-4ca4-8032-1bb05702bc9e
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

一般

**【描述】**

应校验内存申请函数的输入参数和返回值

**【正确示例】**

```
```
let size = get_untrusted_size();
assert!(size < 100);
let p = malloc(size);
assert!(!p.is_null());
```

```
**【错误示例】**

```
```
let size = get_untrusted_size();
let p = malloc(size);
```

```
**【修复建议】**

应校验内存申请函数的输入参数和返回值
