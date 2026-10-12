# G.ERR.03 不要使用return、break、continue或抛出异常使finally块非正常结束

- **规则ID**：06c154a6-2e5b-4df5-b57c-d996fb65e5e5
- **更新时间**：2026-04-07 04:25:02

---

**【问题级别】**

一般

**【描述】**

在finally代码块中，直接使用return、break、continue、throw语句，会导致finally代码块无法正常结束。非正常结束的finally代码块会影响try或catch代码块中异常的抛出，也可能会影响方法的返回值。

**【正确示例】**

```
##### 场景1：finally代码块
- 修复示例：删除在finally块中的return语句

```javascript
function foo() {
  try {
    ...
    return 1;
  } catch(err) {
    ...
    return 2;
  } finally {
    console.log('XXX!');  // 符合
  }
}

```

```
**【错误示例】**

```
##### 场景1：finally代码块
- 错误示例：在finally块中使用return语句
```javascript
function foo() {
  try {
    ...
    return 1;
  } catch(err) {
    ...
    return 2;
  } finally {
    return 3;   // 不符合
 }
}
```

```
**【修复建议】**

移除finally块中的return、break、continue、throw语句。
