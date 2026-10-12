# G.NOD.05 禁止日志泄露敏感信息

- **规则ID**：611f95ca-67c1-4a8c-8ece-dbdacdce2652
- **更新时间**：2025-06-05 04:35:00

---

**【问题级别】**

一般

**【描述】**

禁止在日志中记录系统的敏感数据(例如用户密码、秘钥、敏感异常等)，防止产生敏感信息泄露风险。

**【正确示例】**

```
console.log('Login success, user is ' + userName + ', password is ********.');

```
**【错误示例】**

```
console.log('Login success, user is ' + userName + ', password is ' + password + '.');

```
**【修复建议】**

禁止日志泄露敏感信息
