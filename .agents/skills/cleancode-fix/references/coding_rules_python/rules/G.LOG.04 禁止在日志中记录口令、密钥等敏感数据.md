# G.LOG.04 禁止在日志中记录口令、密钥等敏感数据

- **规则ID**：4224e125-a038-4753-8c57-0221ae5e5ba2
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

一般

**【描述】**

在日志中禁止记录口令、密钥等敏感信息，包括这些敏感信息的加密密文，防止产生敏感信息泄露风险。若因为特殊原因必须要记录日志，应该使用固定长度的星号（*）代替这些敏感信息。

**【正确示例】**

```
import logging


...
logging.info("Login success,user is:%s  password is:********", user_name)

```
**【错误示例】**

```
import logging


...
logging.info("Login success,user is:%s  password is:%s", user_name, encrypt(password))

```
**【修复建议】**

1. 禁止在日志中记录口令、密钥等敏感信息，包括这些敏感信息的加密密文。

2. 若因为特殊原因必须要记录日志，应该使用固定长度的星号（*）代替这些敏感信息。
