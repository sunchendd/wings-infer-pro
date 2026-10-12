# G.ERR.03 信号处理命令应使用单引号而不是双引号(试点)

- **规则ID**：513c08fa-5d4a-4818-a3ad-a933a6a439f6
- **更新时间**：2025-06-05 04:30:00

---

**【问题级别】**

严重

**【描述】**

如果采用双引号书写信号处理操作，那么双引号中的变量值会在当前Shell环境中进行展开而不是等到信

号处理时再展开。

**【正确示例】**

```
#!/bin/bash
  # 符合：echo显示的时间为捕获信号时的时间
  trap 'echo User signal is received on $(date)' SIGINT
  # 符合：echo显示的时间为捕获信号时的时间
  trap "echo User signal is received on "'$(date)' SIGINT

```
**【错误示例】**

```
#!/bin/bash
  # 不符合：echo显示的时间为执行trap命令的时间，而不是捕获信号时的时间
  trap "echo User signal is received on $(date)" SIGINT

```
**【修复建议】**

信号处理命令使用单引号包裹
