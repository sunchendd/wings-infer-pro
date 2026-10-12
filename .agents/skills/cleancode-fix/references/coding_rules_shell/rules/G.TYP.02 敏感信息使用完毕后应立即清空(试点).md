# G.TYP.02 敏感信息使用完毕后应立即清空(试点)

- **规则ID**：09210e78-a6fa-4fcc-9cd8-d258fe6edd77
- **更新时间**：2025-06-05 04:30:01

---

**【问题级别】**

严重

**【描述】**

敏感信息使用完毕后应立即清空。

**【正确示例】**

```
#!/bin/bash
if [[ -n "${fd_pword}" ]]; then
    do_something_function "${fd_pword}"
    unset fd_pword
fi

```
**【错误示例】**

```
#!/bin/bash
if [[ -n "${fd_pword}" ]]; then
    do_something_function "${fd_pword}"
fi

```
**【修复建议】**

请使用unset命令清除已使用过的敏感信息变量。
