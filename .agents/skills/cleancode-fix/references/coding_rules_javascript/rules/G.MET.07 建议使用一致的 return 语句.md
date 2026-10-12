# G.MET.07 建议使用一致的 return 语句

- **规则ID**：4e187168-8c38-400e-afed-a8dfc8abc3d4
- **更新时间**：2025-06-05 04:25:01

---

**【问题级别】**

提示

**【描述】**

函数内，应使用一致的return语句。

**【正确示例】**

```
function doSomething(condition) {
  if (condition) {
    ...
    return true;
  }
  ...
  return false;
}

```
**【错误示例】**

```
function doSomething(condition) {
  if (condition) {
    ...
    return true;
  }
}

```
**【修复建议】**

必须使用一致的 return 语句
