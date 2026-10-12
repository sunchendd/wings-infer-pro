# G.DCL.01 声明变量时要求使用 const 或 let 而不是 var（ECMAScript 6）

- **规则ID**：30523c6a-4d57-4e36-b0ac-2623ea8f8442
- **更新时间**：2026-04-07 04:25:00

---

**【问题级别】**

一般

**【描述】**

var声明的变量，会被提升到该作用域的顶端。与var不同，let和const是块级作用域，它们声明的变量不会被提升到作用域顶端，这可以帮助程序员避免错误。

**【正确示例】**

```
##### 场景1：声明变量
- 修复示例：只读变量用const定义，其他变量用let定义。

```javascript
const number = 1;   // 符合, 用const定义只读变量number
let count = 1;   // 符合, 用let定义变量count
if (isOK) {
  count += 1;
}
```

```
**【错误示例】**

```
##### 场景1：声明变量
- 错误示例：使用var声明变量。
```javascript
var number = 1;  // 不符合
var count = 1;  // 不符合
if (isOK) {
  count += 1;
}
```

```
**【修复建议】**

在 ECMAScript 6中，只读变量用const定义，其他变量用let定义。
