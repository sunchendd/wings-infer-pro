# G.ERR.03 信号处理命令应使用单引号而不是双引号

- **规则ID**：07a6f7f1-76f4-41c8-9e8b-b5643c39cce5
- **更新时间**：2026-04-07 04:30:01

---

**【问题级别】**

严重

**【描述】**

如果采用双引号书写信号处理操作，那么双引号中的变量值会在当前Shell环境中进行展开而不是等到信号处理时再展开。

**【正确示例】**

```
```shell
#!/bin/bash
# 符合：echo显示的时间为捕获信号时的时间
trap 'echo User signal is received on $(date)' SIGINT
# 符合：echo显示的时间为捕获信号时的时间
trap "echo User signal is received on "'$(date)' SIGINT
```

```
**【错误示例】**

```
```shell
#!/bin/bash
# 不符合：echo显示的时间为执行trap命令的时间，而不是捕获信号时的时间
trap "echo User signal is received on $(date)" SIGINT
```

```
**【修复建议】**

信号处理命令使用单引号包裹。
