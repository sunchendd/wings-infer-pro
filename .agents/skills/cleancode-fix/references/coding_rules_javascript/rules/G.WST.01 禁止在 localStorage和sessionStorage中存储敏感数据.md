# G.WST.01 禁止在 localStorage和sessionStorage中存储敏感数据

- **规则ID**：4f131c27-5bb2-44ef-b675-31212df66f91
- **更新时间**：2025-06-05 04:25:02

---

**【问题级别】**

严重

**【描述】**

localStorage和sessionStorage本身无防XSS的机制，数据容易被窃取，即使对敏感数据加密，一旦密钥泄露，也将导致敏感数据泄露。

**【正确示例】**

```
localStorage.setItem('name', name);

```
**【错误示例】**

```
localStorage.setItem('password', password);

```
**【修复建议】**

禁止在 localStorage和sessionStorage中存储敏感数据
