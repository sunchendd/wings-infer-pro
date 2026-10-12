# G.MET.09 不要给函数的入参重新赋值

- **规则ID**：d299d61f-a150-4c9d-afe2-6c0f7bbad2cf
- **更新时间**：2026-04-07 04:35:01

---

**【问题级别】**

提示

**【描述】**

对函数参数中的变量重新赋值可能会误导读者，导致混乱，也会改变 arguments 对象。

**【正确示例】**

```
##### 场景1：函数的入参
- 修复示例：函数内部对入参的值赋值给另一个变量

```javascript
function foo(bar) {
  const baz = bar;
  ...
}
```
##### 场景2：
- 修复示例：使用参数默认值的方式。

```javascript
function handleThings(opts = {}) {
  ...
}
```

```
**【错误示例】**

```
##### 场景1：函数的入参
- 错误示例：函数内部对入参重新赋值。

```javascript
function foo(bar) {
  bar.aaa++;
}
```
##### 场景2：
- 错误示例：函数内给参数赋初值。

```javascript
function handleThings(opts) {
  // 如果参数 opts 是 false 或 空字符串 的话，下面的做法会把它设定为一个对象，这可能会造成意外的错误
  opts = opts || {};
  ...
}
```

```
**【修复建议】**

不要给函数的入参重新赋值。
