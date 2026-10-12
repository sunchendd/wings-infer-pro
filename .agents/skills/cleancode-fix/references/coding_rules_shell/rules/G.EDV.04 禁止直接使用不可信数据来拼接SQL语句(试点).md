# G.EDV.04 禁止直接使用不可信数据来拼接SQL语句(试点)

- **规则ID**：0fb5a4f9-cfc4-49f2-9fa7-001c2232b453
- **更新时间**：2025-06-05 04:30:00

---

**【问题级别】**

严重

**【描述】**

SQL注入是指原始SQL操作被动态更改成一个与程序预期完全不同的操作。执行更改后SQL可能导致信

息泄露或数据被篡改。防止SQL注入主要需对不可信数据进行校验。推荐对不可信数据做如下校验以防

止SQL注入：

- 对于字符型字段，需对输入数据做转义

  - 将单引号替换为斜杠+单引号。

  - 如果字符型输入数据作为SQL语句中like部分，需参考《Shell语言编程规范V2.0(试行)》附录A做转义

  - 系统根据具体业务场景，确定需要校验的特殊字符，特殊字符可以参考《Shell语言编程规范V2.0(试行)》 附录A和附录B。

-  对于整型字段，需对输入数据进行类型检测，拒绝传入不合法数字

**【正确示例】**

```
#!/bin/bash
  local username="$1"
  read -s pvalue
  # 增加参数校验
  if [[ ! "${username}" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]]; then
  # 出错处理
  echo ""
  fi
  # 增加参数校验
  echo "${pvalue}" | grep "^.\{8,30\}$" | grep "[a-z]" | grep "[A-Z]" | grep "[0-9]" | grep "[~@#$%^&*()_=+]" &> /dev/null
  if [$? -ne 0 ]; then
  # 出错处理
  echo exit 1
  fi
  local sql="SELECT * FROM db_user WHERE username = '${username}' AND password= '${pvalue}'"

```
**【错误示例】**

```
#!/bin/bash
  local username="$1"
  read -s pvalue
  # 没有校验输入参数就直接拼装成SQL并使用
  local sql="SELECT * FROM db_user WHERE username = '${username}' AND password= '${pvalue}'"

```
**【修复建议】**

在拼接sql语句时需对外部输入的数据进行校验
