# G.AST.03-TS 使用可选链操作符?.替代非空判断

- **规则ID**：9d66e767-5a8a-426d-af1d-bcbfbacd1f44
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

提示

**【描述】**

TypeScript 3.7 开始支持可选链操作符`?.`，该操作符能支持在前置对象非空的时候才取下一级属性的值，能够安全地引用潜在为 `null` 或 `undefined` 的变量。

**【正确示例】**

```
##### 场景1：可选链操作符
- 修复示例：可选链操作符`?.`，代码简洁易懂。

```javascript
foo?.a?.b?.method?.();

return foo?.a?.b?.c;

```

```
**【错误示例】**

```
##### 场景1：可选链操作符
- 错误示例：进行一系列的非空判断，代码冗余。
```javascript
foo && foo.a && foo.a.b && foo.a.b.method && foo.a.b.method();

if (foo === null || foo === undefined ||
  foo.a === null || foo.a === undefined ||
  foo.a.b === null || foo.a.b === undefined ) {
  return undefined;
} else {
  return foo.a.b.c;
}
```

```
**【修复建议】**

使用可选链操作符`?.`替代非空判断。
