# G.TRA.BLN.01 宜使用具体类型的 default() 方法代替  Default::default() 调用-试行

- **规则ID**：1e83bf15-8966-4563-9666-bb30468e640f
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

为了增强可读性。

**【正确示例】**

```
let s = String::default();

```
**【错误示例】**

```
let s: String = Default::default();

```
**【修复建议】**
