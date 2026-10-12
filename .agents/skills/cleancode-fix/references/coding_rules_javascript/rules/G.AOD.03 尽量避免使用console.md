# G.AOD.03 尽量避免使用console

- **规则ID**：cb530577-f175-45d1-b6f3-0e9ee63f7baf
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

提示

**【描述】**

在 JavaScript，虽然console 被设计为在浏览器中执行的，但避免使用 console 的方法被认为是一种最佳实践。这样的消息被认为是用于调试的，因此不适合输出到客户端。通常，在发布正式交付的产品之前尽量删除不必要 

 的 console 调用。

**【正确示例】**

```
##### 场景1：console打印
- 修复示例：使用自定义函数打印信息

```javascript
Console.log("Hello world!");
```

```
**【错误示例】**

```
##### 场景1：console打印
- 错误示例：使用console打印信息

```javascript
console.log("Log a debug level message.");
```

```
**【修复建议】**

尽量避免使用console。
