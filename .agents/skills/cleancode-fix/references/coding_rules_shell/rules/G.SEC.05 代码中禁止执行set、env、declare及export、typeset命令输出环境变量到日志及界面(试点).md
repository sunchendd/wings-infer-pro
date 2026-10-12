# G.SEC.05 代码中禁止执行set、env、declare及export、typeset命令输出环境变量到日志及界面(试点)

- **规则ID**：c0b5f3f5-1731-4189-abb7-53fc99d9a8d1
- **更新时间**：2025-06-05 04:30:01

---

**【问题级别】**

严重

**【描述】**

set、env、declare及export、typeset命令会把操作系统的环境变量显示出来，如果其中存在敏感信息，则易造成敏感信息泄漏。

**【正确示例】**

```
#!/bin/bash
  set +x  # 带参数的set命令不会打印环境变量信息
  env -i  # env命令-i, --ignore-environment, -C, --chdir=DIR, --help, --version时不会打印环境变量信息
  declare -a a=(1 2 3)
  typeset -A b=(['a']=1)
  export foo='bar'

```
**【错误示例】**

```
#!/bin/bash
  # 不符合：无参使用set、env、declare及export、typeset命令会打印环境变量信息
  set
  env
  declare
  typeset
  export

```
**【修复建议】**

- 不要无参使用set、env、declare及export、typeset命令

- env 命令在只有参数-i, --ignore-environment, -C, --chdir=DIR, --help, --version时不会打印

- declare、typeset命令无参数或使用-f -p参数时会把操作系统的环境变量显示出来

- export命令无参数或使用-n -p参数（不带其他参数）时会把操作系统的环境变量显示出来，易造成敏感信息泄漏
