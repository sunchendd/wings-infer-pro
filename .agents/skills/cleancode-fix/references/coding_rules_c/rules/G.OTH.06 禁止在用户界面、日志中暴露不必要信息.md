# G.OTH.06 禁止在用户界面、日志中暴露不必要信息

- **规则ID**：34eed01c-e790-4e5c-8274-e6b8ef17a89a
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

检查是否打印敏感信息

**【正确示例】**

```
```
void SensitiveDataLeakGoodCase01(FILE *userdb)
{
    char uname[MAX_UNAME_LEN];
    if (!fgets(uname, sizeof(uname), stdin)) {
        return;
    }
    char *pwd = getpass("Please enter your password: ");
    /* 符合: */
    fprintf(userdb, "%s:%s
", "******", "******");
    return;
}
```

```
**【错误示例】**

```
```
void SensitiveDataLeakBadCase01(FILE *userdb)
{
    char uname[MAX_UNAME_LEN];
    if (!fgets(uname, sizeof(uname), stdin)) {
        return;
    }
    char *pwd = getpass("Please enter your password: ");
    /* 不符合: 查找不加密的情况下将用户名和密码存储到文件系统 */
    fprintf(userdb, "%s:%s
", uname, pwd);
    return;
}
```

```
**【修复建议】**

建议不要打印敏感信息，使用通配符或者直接删除对应打印语句。
