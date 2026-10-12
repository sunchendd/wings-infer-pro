# G.TYP.05-TS 复杂的数组类型使用Array<T>声明

- **规则ID**：a7547638-1c35-47e8-9f08-c9d5c4785292
- **更新时间**：2025-06-05 04:35:03

---

**【问题级别】**

提示

**【描述】**

复杂的数组类型（联合类型、交叉类型、对象类型、函数类型等）使用Array<T>。

**【正确示例】**

```
const foo: Array<string | number> = ['a', 'b']; // 联合类型，使用Array<T>
const man: Array<IPerson | IWorker> = ['a', 'b']; // 交叉类型，使用Array<T>
const bar: Array<{ prop: string }> = [{ prop: 'a' }]; // 对象类型，使用Array<T>
const car: Array<() => void> = [() => {}]; // 函数类型，使用Array<T>

```
**【错误示例】**

```
const foo: (string | number)[] = ['a', 'b']; // 联合类型，使用T[]
const man: (IPerson | IWorker)[] = ['a', 'b']; // 交叉类型，使用T[]
const bar: { prop: string }[] = [{ prop: 'a' }]; // 对象类型，使用T[]
const car: (() => void)[] = [() => {}]; // 函数类型，使用T[]

```
**【修复建议】**

复杂的数组类型使用Array<T>声明
