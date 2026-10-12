# G.MET.05 函数的参数个数不建议超过 5 个

- **规则ID**：5fa8bac4-77aa-4afe-a3a5-9e0c8be59ae3
- **更新时间**：2025-06-05 04:35:03

---

**【问题级别】**

提示

**【描述】**

如果参数超过5个，则维护的难度很大，建议减少参数个数。

**【正确示例】**

```
function insertHistory(spWorkfLog) { ... }

```
**【错误示例】**

```
function insertHistory(workfSeq, workfType, recSeq, sortOrder, orderSeq, workfID, region, subSys, orderID, procSystem, platType, neID, telnum, imsi, orderPri) { ... }

```
**【修复建议】**

函数的参数个数不建议超过 5 个
