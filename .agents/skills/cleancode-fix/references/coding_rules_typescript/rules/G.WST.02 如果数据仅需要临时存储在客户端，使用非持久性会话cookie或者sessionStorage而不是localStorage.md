# G.WST.02 如果数据仅需要临时存储在客户端，使用非持久性会话cookie或者sessionStorage而不是localStorage

- **规则ID**：0c573ffe-820d-40a8-b942-3e15213316b3
- **更新时间**：2025-06-05 04:35:00

---

**【问题级别】**

一般

**【描述】**

localStorage是持久性（没有时间限制）的数据存储，数据永远不会过期的，除非主动删除数据，不应该用于存储临时数据，否则会导致数据长期存留，增加数据泄露的风险，同时，浪费客户端的磁盘空间。而存储于非持久性会话cookie或sessionStorage中的数据会被及时清除。

**【正确示例】**

```
localStorage.setItem('key',value);

```
**【错误示例】**

```
localStorage.setItem('key',temp);

```
**【修复建议】**

如果数据仅需要临时存储在客户端，使用非持久性会话cookie或者sessionStorage而不是localStorage
