# G.DCL.05 不要使用 undefined 初始化变量

- **规则ID**：041d1e29-f360-4436-8d66-6ba2bae78368
- **更新时间**：2026-04-07 04:35:00

---

**【问题级别】**

一般

**【描述】**

在 JavaScript 中，声明一个变量但未初始化，变量会自动获得 undefined 作为初始值。因此，初始化变量值为 undefined 是多余的。

**【正确示例】**

```
##### 场景1：变量初始化
- 修复示例：可以直接声明一个变量且不对其初始化。

```javascript
let foo;
```

```
**【错误示例】**

```
```ts
/*eslint no-undef-init: "error"*/
/*eslint-env es6*/

var foo = undefined;
let bar = undefined;
```

```
**【修复建议】**

不使用 undefined 初始化变量。
