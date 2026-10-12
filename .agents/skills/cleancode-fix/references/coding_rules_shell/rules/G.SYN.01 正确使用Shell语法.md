# G.SYN.01 正确使用Shell语法

- **规则ID**：ed3e33cb-fc0e-41c3-8aca-1df7e118ae60
- **更新时间**：2026-04-07 04:30:01

---

**【问题级别】**

严重

**【描述】**

编写语法正确的、能被解释器正确解析的脚本。 避免语法错误导致程序运行异常。  

例如()、[]、do\done、EOF、if\fi的成对出现，空格的正确使用等。  

此规则仅覆盖解析语法树异常的场景

**【正确示例】**

```
#!/bin/bash

# 变量取值的正确用法
name="abc" && echo "Hello ${name}"

# 变量取值的正确用法
USER="abc" && echo "${USER}"

```
**【错误示例】**

```
#!/bin/bash

# 输出告警信息：invalid parameter name
name="abc" && echo "Hello ${{name}" # 不符合：不匹配的{}

# 输出告警信息：parameter expansion requires a literal
USER="abc" && echo ${"USER"} # 不符合： 双引号必须写在${}的外面

```
**【修复建议】**

使用正确的shell语法编写脚本
