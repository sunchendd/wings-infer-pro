# Forbid_Hard-coded_Password

- **规则ID**：538f57c3-5aca-4c50-a4ec-385d8960e5d9
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

硬编码的密码可能会被滥用以获取未经授权的访问并破坏安全边界。

**【正确示例】**

```


```
**【错误示例】**

```
def bad():
    DB_passwd = "Password1"
    return DB_passwd

```
**【修复建议】**
