# G.SYN.01 正确使用Shell语法(试点)

- **规则ID**：e9f339ec-cfdd-49b5-8d83-20cf5f78aed4
- **更新时间**：2025-06-05 04:30:01

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
