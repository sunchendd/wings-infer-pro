# G.CTF.02 if条件表达式分支中如果包含了else if分支也应该包含else分支-试行

- **规则ID**：94b09c15-6c9f-4a28-9a80-c605db0786f6
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**



**【正确示例】**

```
# fn a() {}
# fn b() {}
# let x: i32 = 1;
if x.is_positive() {
    a();
} else if x.is_negative() {
    b();
} else {
    // We don't care about zero.
}

```
**【错误示例】**

```
# fn a() {}
# fn b() {}
# let x: i32 = 1;
if x.is_positive() {
    a();
} else if x.is_negative() {
    b();
}

```
**【修复建议】**
