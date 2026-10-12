# G.WST.02 如果数据仅需要临时存储在客户端，使用非持久性会话cookie或者sessionStorage而不是localStorage

- **规则ID**：b29898fc-2ea2-4444-9621-2ae81bbb81d3
- **更新时间**：2025-06-05 04:25:02

---

**【问题级别】**

一般

**【描述】**

localStorage是持久性（没有时间限制）的数据存储，会导致数据长期存留，增加数据泄露的风险。存储于非持久性会话cookie或sessionStorage中的数据会被及时清除。

**【正确示例】**

```
sessionStorage.setItem('tempData', tempData);

```
**【错误示例】**

```
localStorage.setItem('tempData', tempData);

```
**【修复建议】**

如果数据仅需要临时存储在客户端，使用非持久性会话cookie或者sessionStorage而不是localStorage
