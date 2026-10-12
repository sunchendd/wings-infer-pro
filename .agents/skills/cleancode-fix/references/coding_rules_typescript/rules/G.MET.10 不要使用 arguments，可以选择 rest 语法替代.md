# G.MET.10 不要使用 arguments，可以选择 rest 语法替代

- **规则ID**：d65c6a61-02ef-4525-ab31-81b1005471fb
- **更新时间**：2026-04-07 04:35:01

---

**【问题级别】**

一般

**【描述】**

rest 参数是一个真正的数组，也就是说能够在它上面直接使用所有的数组方法，比如 sort，map，forEach或pop，而 arguments 是一个类数组。因此，应选择使用rest语法替代arguments。另外，rest参数必须是列表中的最后一个参数。

**【正确示例】**

```
##### 场景1：rest 语法
- 修复示例：使用 rest 语法

```javascript
function concatenateAll(...args) {
  return args.join('');
}
```
##### 场景2：rest 作为最后一个参数
- 修复示例：函数声明使用 rest 作为最后一个参数

```javascript
function foo(action, ...args) {
  action.apply(null, args);
}
```

```
**【错误示例】**

```
##### 场景1：rest 语法
- 错误示例：使用 arguments

```javascript
function concatenateAll() {
  // 因为arguments是类数组，不能直接使用join方法，需要先转换为真正的数组
  const args = Array.prototype.slice.call(arguments);   
  return args.join('');
}
```
##### 场景2：rest 作为最后一个参数
- 错误示例：函数声明有一个参数，使用 arguments

```javascript
function foo(action) {
  var args = Array.prototype.slice.call(arguments, 1);
  action.apply(null, args);
}
```

```
**【修复建议】**

不要使用 arguments，可以选择 rest 语法替代。
