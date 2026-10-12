# G.CMT.01-TS 使用// @ts-<directive>注释时必须添加说明

- **规则ID**：37b52d76-1cb2-42cd-9022-a5761e59be19
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

一般

**【描述】**

TS语法支持下面4种抑制错误的语法，要求使用下面语法时必须在指令后面增加说明。



 // @ts-expect-error

 // @ts-ignore

 // @ts-nocheck

 // @ts-check

**【正确示例】**

```
##### 场景1：使用// @ts-<directive>注释
- 修复示例：使用// @ts-expect-error注释时添加说明

```typescript
if (false) {
  // @ts-expect-error: Unreachable code error
  console.log('hello');
}
```

```
**【错误示例】**

```
##### 场景1：使用// @ts-<directive>注释
- 错误示例：使用// @ts-expect-error注释时没有添加说明

```typescript
if (false) {
  // @ts-expect-error
  console.log('hello');
}
```

```
**【修复建议】**

使用// @ts-<directive>注释时必须添加说明。
