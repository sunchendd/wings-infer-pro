# G.CMT.02-TS 建议使用// @ts-expect-error代替// @ts-ignore忽略错误检查

- **规则ID**：e13c2e73-79ba-4727-b615-9f1f7a8c9e03
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

提示

**【描述】**

推荐使用// @ts-expect-error 代替// @ts-ignore，// @ts-expect-error当且仅当代码存在错误时起作用，// @ts-expect-error注释下的代码无错误时，会出现Unused '@ts-expect-error' directive.提示，而// @ts-ignore 

 则不会有任何提示。

**【正确示例】**

```
##### 场景1：忽略错误检查
- 修复示例：使用// @ts-expect-error

```typescript
if (false) {
  // @ts-expect-error: Unreachable code error
  console.log('hello');
}
```

```
**【错误示例】**

```
##### 场景1：忽略错误检查
- 错误示例：使用// @ts-ignore

```typescript
if (false) {
  // @ts-ignore: Unreachable code error
  console.log('hello');
}
```

```
**【修复建议】**

建议使用// @ts-expect-error代替// @ts-ignore忽略错误检查。
