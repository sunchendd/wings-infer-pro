# G.TYP.03-TS 接口、类、类型别名的声明使用 ; 分隔符号

- **规则ID**：94429ff7-d6e7-4587-a858-4ae302f4e9ce
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

提示

**【描述】**

当接口、类、类型别名的声明包含多行时，建议使用分号隔开，有利于提高可读性。

**【正确示例】**

```
##### 场景1：接口声明
- 修复示例：使用(;)分隔符。
```javascript
interface Foo {
  name: string;
  greet(): string;
}
```
##### 场景2：接口声明
- 修复示例：接口声明多行时，最后一行需要使用(;)分隔符。
```javascript
interface Baz {
  name: string;
  greet(): string;
}
```
##### 场景3：类型别名声明
- 修复示例：单行时，最后一个成员后面不需要使用(;)分隔符。
```javascript
type FooBar = { name: string; greet(): string }
```

```
**【错误示例】**

```
##### 场景1：接口声明
- 错误示例：接口的声明没有使用分号作为分隔符。
 ```javascript
// 缺少分隔符
interface Foo {
  name: string
  greet(): string
}

// 应该使用(;)分隔符
interface Bar {
  name: string,
  greet(): string,
}
```
##### 场景2：接口声明
- 错误示例：接口声明多行时，最后一行缺少(;)分隔符。
```javascript
interface Baz {
  name: string;
  greet(): string     
}
```
##### 场景3：类型别名声明
- 错误示例：单行时，最后一个成员后面仍然使用(;)分隔符。
```javascript
type FooBar = { name: string; greet(): string; }
```

```
**【修复建议】**

1. 接口、类、类型别名的声明使用 `;` 分隔符号。

2. 单行最后一个成员不需要分隔符，多行则需要。
