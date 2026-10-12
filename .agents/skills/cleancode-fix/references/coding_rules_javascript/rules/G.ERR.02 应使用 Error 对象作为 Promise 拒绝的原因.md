# G.ERR.02 应使用 Error 对象作为 Promise 拒绝的原因

- **规则ID**：890f1d03-8503-49cf-9b33-966f45aac7d7
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

提示

**【描述】**

在 Promise 中只传递内置的 Error 对象实例给 reject() 函数作为自定义错误，被认为是个很好的实践。Error 对象会自动存储堆栈跟踪，在调试时，通过它可以用来确定错误是从哪里来的。如果 Promise 使用了非 Error 的值 

 作为拒绝原因，那么就很难确定 reject 在哪里产生。

**【正确示例】**

```
##### 场景1：Promise
- 修复示例：使用 Error 对象作为 Promise 拒绝的原因

```javascript
Promise.reject(new Error('something bad happened'));
```

```
**【错误示例】**

```
##### 场景1：Promise
- 错误示例：使用了非 Error 的值  作为 Promise 拒绝原因

```javascript
Promise.reject('something bad happened');
```

```
**【修复建议】**

应使用 Error 对象作为 Promise 拒绝的原因。
