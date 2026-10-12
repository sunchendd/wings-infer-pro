# G.FMT.12-CPP 避免将if/else/else if写在同一行

- **规则ID**：ebeb62a2-3f88-4032-bb6e-6980fd859fd8
- **更新时间**：2025-03-25 19:21:55

---

**【问题级别】**

一般

**【描述】**

条件语句中，若有多个分支，应该写在不同行。

**【正确示例】**

```
if (someConditions) {
    DoSomething();
    ...
} else {                                 // 符合：else 与 if 在不同行
    ...
}

```
**【错误示例】**

```
if (someConditions) { ... } else { ... } // 不符合：else 与 if 在同一行

```
**【修复建议】**

将语句拆分到多行
