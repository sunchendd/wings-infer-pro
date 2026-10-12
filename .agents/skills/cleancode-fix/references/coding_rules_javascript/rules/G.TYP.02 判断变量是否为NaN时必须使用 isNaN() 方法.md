# G.TYP.02 判断变量是否为NaN时必须使用 isNaN() 方法

- **规则ID**：8b76b35a-fed2-42fc-bda7-e18736cdd3d0
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

一般

**【描述】**

因为在 JavaScript 中 NaN 独特之处在于它不等于任何值，包括它本身，与 NaN 进行比较的结果是令人困惑：NaN !== NaN or NaN != NaN 的值都是 true。

因此，必须使用 Number.isNaN() 或 全局的 isNaN() 函数来测试一个值是否是 NaN。

**【正确示例】**

```
##### 场景1：判断变量是否为NaN
- 修复示例：使用isNaN函数来测试一个值是否是NaN。

```javascript
if (isNaN(foo)) {
  // ...
}

if (!isNaN(foo)) {
  // ...
}
```

```
**【错误示例】**

```
##### 场景1：判断变量是否为NaN
- 错误示例：使用`==`来判断变量是否为NaN。

```javascript
if (foo == NaN) {   
  // ...
}

if (foo != NaN) {
  // ...
}
```

```
**【修复建议】**

使用 Number.isNaN() 或 全局的 isNaN() 函数来测试一个值是否是 NaN。
