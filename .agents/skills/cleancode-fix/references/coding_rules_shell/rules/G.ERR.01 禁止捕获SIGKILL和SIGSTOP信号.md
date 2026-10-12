# G.ERR.01 禁止捕获SIGKILL和SIGSTOP信号

- **规则ID**：2846b0aa-220b-4e03-9415-d76065fc4472
- **更新时间**：2026-04-07 04:30:00

---

**【问题级别】**

严重

**【描述】**

SIGKILL和SIGSTOP信号不能被捕获。

**【正确示例】**

```
```shell
#!/bin/bash
# 符合：捕获SIGINT信号
trap 'my_trap' SIGINT
```

```
**【错误示例】**

```
```shell
#!/bin/bash
# 不符合：捕获了SIGKILL信号
trap 'my_trap' SIGKILL

# 不符合：捕获了SIGSTOP信号
trap 'my_trap' SIGSTOP
```

```
**【修复建议】**

禁止trap命令捕获SIGKILL和SIGSTOP信号。
