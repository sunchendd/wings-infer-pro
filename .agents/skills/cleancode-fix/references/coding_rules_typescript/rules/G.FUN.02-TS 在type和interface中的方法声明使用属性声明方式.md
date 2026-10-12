# G.FUN.02-TS 在type和interface中的方法声明使用属性声明方式

- **规则ID**：73f65112-e95d-46c0-9999-78b3d08273d6
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

提示

**【描述】**

建议统一风格，在type和interface中的方法声明使用属性声明方式。

**【正确示例】**

```
##### 场景1：声明方式
- 修复示例：在type和interface中的方法声明使用属性声明方式

```typescript
interface T1 {
  func: (arg: string) => number;
}
type T2 = {
  func: (arg: boolean) => void;
};
interface T3 {
  func: ((arg: number) => void) &
    ((arg: string) => void) &
    ((arg: boolean) => void);
}
```

```
**【错误示例】**

```
##### 场景1：声明方式
- 错误示例：在type和interface中的方法声明使用函数的声明方式

```typescript
interface T1 {
  func(arg: string): number;
}
type T2 = {
  func(arg: boolean): void;
};
interface T3 {
  func(arg: number): void;
  func(arg: string): void;
  func(arg: boolean): void;
}
```

```
**【修复建议】**

在type和interface中的方法声明使用属性声明方式。
