# G.DCL.04 禁止连续赋值

- **规则ID**：215eed95-8859-4795-9477-413834f96127
- **更新时间**：2026-04-07 04:25:00

---

**【问题级别】**

一般

**【描述】**

对变量连续赋值可能会创建隐藏的全局变量，从而导致意想不到的结果。

**【正确示例】**

```
##### 场景1：变量赋值
- 修复示例：每个变量单独一个赋值语句。

```javascript
(function example() {
  let a = 1;   // 符合
  let b = a;   // 符合
  let c = a;   // 符合
}());

console.log(a); // a is not defined
console.log(b); // b is not defined
console.log(c); // c is not defined
```

```
**【错误示例】**

```
##### 场景1：变量赋值
- 错误示例：对多个变量连续赋值变量。

```javascript
(function example() {
  // JavaScript 将其解释为 let a = ( b = ( c = 1 ) )，其中let 关键字只适用于变量 a， 变量 b 和 c 变为全局变量。
  let a = b = c = 1;   // 不符合
}());

console.log(a); //  a is not defined
console.log(b); // 1
console.log(c); // 1

```

```
**【修复建议】**

一条语句只对一个变量赋值。
