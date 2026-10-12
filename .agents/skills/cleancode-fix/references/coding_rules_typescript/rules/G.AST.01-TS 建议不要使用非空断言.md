# G.AST.01-TS 建议不要使用非空断言

- **规则ID**：ad340561-8632-4992-b6cf-6c8993fcf887
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

提示

**【描述】**

非空断言将忽略空值检查，可能导致运行时出现空值异常，建议尽量不要使用该特性。

**【正确示例】**

```
##### 场景1：非空断言
- 修复示例：使用可选链操作符来代替非空断言操作符。
```javascript
interface Foo {
  cat: string;
  bar?: string;
}

const foo: Foo = getFoo();
// bar属性不存在时使用默认值false
const includesBaz: boolean = foo.bar?.includes('baz') ?? false;  // 符合
```

```
**【错误示例】**

```
##### 场景1：非空断言
- 错误示例：使用了非空断言，导致代码可能会出现异常。

```javascript
interface Foo {
  cat: string;
  bar?: string;
}

// getFoo()返回的对象可能没有bar属性
const foo: Foo = getFoo();
// bar属性不存在时会出现异常
const includesBaz: boolean = foo.bar!.includes('baz');  // 不符合
```

```
**【修复建议】**

将!.修改为?. 不要使用 ! 后缀运算符进行非空断言。
