# G.FMT.09 建议 if、for、do、while 等语句的执行体加大括号 {}

- **规则ID**：18085fa1-4ea0-44b9-bfdc-bcb568d3b797
- **更新时间**：2026-04-07 04:25:00

---

**【问题级别】**

提示

**【描述】**

在if、for、do、while 等语句的执行体加大括号 {}是一种最佳实践，因为省略大括号容易导致错误，并且降低代码的清晰度。

**【正确示例】**

```
##### 场景1：大括号
- 修复示例： if、for、do、while 等语句的执行体任何时候都添加大括号 {}。
```javascript
if (foo) {
  foo++;
}

while (bar) {
  baz();
}

if (foo) {
  baz();
} else {
  qux();
}
```

```
**【错误示例】**

```
##### 场景1：大括号
- 错误示例： if、for、do、while 等语句的执行体 省略了大括号 {}。
```javascript
if (foo) foo++;

while (bar)
  baz();

if (foo) {
  baz();
} else qux();
```

```
**【修复建议】**

建议 if、for、do、while 等语句的执行体加大括号 {}。
