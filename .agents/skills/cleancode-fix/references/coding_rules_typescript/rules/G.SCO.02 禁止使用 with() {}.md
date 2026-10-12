# G.SCO.02 禁止使用 with() {}

- **规则ID**：d2005023-683a-48da-9e9b-2a69515a9657
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

一般

**【描述】**

使用with让代码在语义上变得不清晰，因为with的对象，可能会与局部变量产生冲突，从而改变程序原本的用义。

**【正确示例】**

```
##### 场景1：with
- 修复示例：不使用with语句。

```javascript
const foo = { x: 5 }；
let x = 3;
console.log(x);  // x = 3
console.log(foo.x);  // x = 3
```

```
**【错误示例】**

```
##### 场景1：with
- 错误示例： 使用with语句。

```javascript
const foo = { x: 5 };

with (foo) {       
  var x = 3;
  console.log(x);  // x = 3
}
console.log(foo.x);  // x = 3

```

```
**【修复建议】**

禁止使用with()。
