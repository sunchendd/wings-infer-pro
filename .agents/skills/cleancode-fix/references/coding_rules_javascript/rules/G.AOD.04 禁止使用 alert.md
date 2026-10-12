# G.AOD.04 禁止使用 alert

- **规则ID**：36b8d4c0-27db-4b36-b065-6f3105f9ce25
- **更新时间**：2026-04-07 04:25:01

---

**【问题级别】**

一般

**【描述】**

JavaScript 的 alert、confirm 和 prompt 被广泛认为是突兀的 UI 元素，应该被一个更合适的自定义的 UI 界面代替。此外，alert 经常被用于调试代码，部署到生产环境之前应该全部删除。

**【正确示例】**

```
##### 场景1：alert
- 修复示例：采用自定义方法

```javascript
customAlert("Something happened!");

customConfirm("Are you sure?");

customPrompt("Who are you?");
```

```
**【错误示例】**

```
##### 场景1：alert
- 错误示例：使用alert、confirm 和 prompt方法

```javascript
alert("here!");

confirm("Are you sure?");

prompt("What's your name?", "John Doe");
```

```
**【修复建议】**

禁止使用 alert。
