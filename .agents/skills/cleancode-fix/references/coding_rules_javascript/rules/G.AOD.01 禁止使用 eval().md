# G.AOD.01 禁止使用 eval()

- **规则ID**：aa532070-fd3d-40bf-9b54-f9d02c337cdf
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

一般

**【描述】**

使用eval()不仅会使程序的可读性变差，而且，当 eval() 里面包含用户输入的话存在安全风险。在不可信的代码里使用 eval() 有可能使程序受到不同的注入攻击。

**【正确示例】**

```
##### 场景1：eval
- 修复示例：使用JSON的parse方法来分析 JSON 字符串

```javascript
const feed = '{ "name": "Alice", "id": 31502 }';
const userInfo = JSON.parse(feed);  // 符合
const id = userInfo.id;
```

```
**【错误示例】**

```
##### 场景1：eval
- 错误示例：使用eval()来解析对象。

```javascript
const feed = '{ "name": "Alice", "id": 31502 }';
const userInfo = eval(feed);  // 不符合，使用eval()函数
const id = userInfo.id;

```

```
**【修复建议】**

移除eval()函数，建议用其它更佳、更清晰、更安全的方式写代码，比如，使用JSON的parse方法来分析JSON字符串。
