# G.TYP.02 敏感信息使用完毕后应立即清空

- **规则ID**：52cfecd0-480b-40af-9660-ab4b7c3e795b
- **更新时间**：2026-04-07 04:30:01

---

**【问题级别】**

严重

**【描述】**

shell中保存敏感信息的变量在使用后应立即使用unset命名清除。

**【正确示例】**

```
```shell
#!/bin/bash
read -rs -p '设置密码' fd_pword
do_something_function ${fd_pword}
unset fd_pword
```

```
**【错误示例】**

```
```shell
#!/bin/bash
read -rs -p '设置密码' fd_pword
do_something_function ${fd_pword}
```

```
**【修复建议】**

保存敏感信息的变量在使用后使用unset命令清除。
