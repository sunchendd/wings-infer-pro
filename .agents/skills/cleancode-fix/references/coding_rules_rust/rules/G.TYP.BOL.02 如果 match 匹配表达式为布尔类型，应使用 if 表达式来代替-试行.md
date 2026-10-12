# G.TYP.BOL.02 如果 match 匹配表达式为布尔类型，应使用 if 表达式来代替-试行

- **规则ID**：10e95e88-1a49-4360-814d-9914de8ab76d
- **更新时间**：2025-06-05 04:40:02

---

**【问题级别】**

严重

**【描述】**

对于布尔表达式更倾向于使用 if ... else ...，相比较 match 模式匹配更有利于代码可读性。

**【正确示例】**

```
# fn foo() {}
# fn bar() {}
let condition: bool = true;
if condition {
    foo();
} else {
    bar();
}

```
**【错误示例】**

```
# fn foo() {}
# fn bar() {}
let condition: bool = true;
match condition {
    true => foo(),
    false => bar(),
}

```
**【修复建议】**
