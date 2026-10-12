# G.FMT.12 每句代码后加分号

- **规则ID**：7acba8e0-0f4d-43a5-bcab-2034662146c9
- **更新时间**：2025-06-05 04:35:01

---

**【问题级别】**

提示

**【描述】**

建议任何时候都不要省略它。

**【正确示例】**

```
const foo = myfoo; // 赋值
(function(){
  const name = 'Skywalker';
  return name;
})(); // 自执行函数

```
**【错误示例】**

```
const foo = myfoo // 没有分号，会连着下一行一起解析，变成调用myfoo(fn)();
(function(){
  const name = 'Skywalker'
  return name
})(); // 自执行函数

```
**【修复建议】**

建议任何时候都不要省略它。
