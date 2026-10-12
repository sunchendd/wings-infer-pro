# G.AOD.02 禁止使用隐式的 eval()

- **规则ID**：0f709ba6-2afc-4c69-b0a7-1eb4970e0f65
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

一般

**【描述】**

setTimeout()、setInterval() 或者 execScript() (仅限IE浏览器)可以把一个javaScript字符串解析为javaScript代码来执行，当javaScript字符串中包含用户不可信输入时，则可能会使程序受到注入攻击。

**【正确示例】**

```
##### 场景1：隐式eval()
- 修复示例：第一个参数封装成函数。

```javascript
setTimeout(function() {  // 符合
  alert('Hi!');
}, 100);

setInterval(function() {  // 符合
  alert('Hi!');
}, 100);

```

```
**【错误示例】**

```
##### 场景1：隐式eval()
- 错误示例：第一个参数为JavaScript 字符串代码。

```javascript
setTimeout('alert("Hi!");', 100);  // 不符合，有注入风险

setInterval('alert("Hi!");', 100);  // 不符合，有注入风险

execScript('alert("Hi!")');  // 不符合，有注入风险

location.href = 'javascript:alert("Hi!")';  // 不符合，有注入风险

```

```
**【修复建议】**

setTimeout()、setInterval() 或者 execScript() 的第一个参数不直接使用JavaScript 字符串代码，建议封装成函数。
