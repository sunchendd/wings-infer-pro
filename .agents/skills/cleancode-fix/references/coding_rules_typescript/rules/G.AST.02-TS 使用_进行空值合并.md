# G.AST.02-TS 使用??进行空值合并

- **规则ID**：1e2889f9-8f52-4660-a111-3b03e212d4f5
- **更新时间**：2025-06-05 04:35:02

---

**【问题级别】**

提示

**【描述】**

在明确需要空值检测时，应当使用??运算符，避免使用||做假值检测来替代；??在变量为undefined 或 null的时候才使用默认值，||则在变量为假值（undefined、null、''、0等）时也会使用默认值。

**【正确示例】**

```
function myFunc(foo: string | null) {
  return foo ?? 'a string';
}

```
**【错误示例】**

```
// 不够精简
function myFunc(foo: string | null) {
  return (foo !== null && foo !== undefined) ? foo : 'a string';
}

```
**【修复建议】**

使用??进行空值合并
