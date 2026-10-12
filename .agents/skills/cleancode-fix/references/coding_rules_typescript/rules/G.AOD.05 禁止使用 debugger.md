# G.AOD.05 禁止使用 debugger

- **规则ID**：5b5e54fd-818e-46d3-ab13-68e2f2c1da0d
- **更新时间**：2026-04-07 04:35:02

---

**【问题级别】**

一般

**【描述】**

debugger 语句用于告诉 JavaScript 执行环境停止执行并在代码的当前位置启动调试器。随着现代调试和开发工具的出现，使用调试器已不是最佳实践。部署到生产环境之前应该删除。

**【正确示例】**

```
##### 场景1：调试
- 修复示例：不使用debugger

```javascript
function isTruthy(x) {
    return Boolean(x); // 在此行设置断点
}
```

```
**【错误示例】**

```
##### 场景1：调试
- 错误示例：使用debugger调试器

```javascript
function isTruthy(x) {
    debugger;
    return Boolean(x);
}
```

```
**【修复建议】**

禁止使用 debugger。
