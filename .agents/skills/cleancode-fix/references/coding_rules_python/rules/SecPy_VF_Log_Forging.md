# SecPy_VF_Log_Forging

- **规则ID**：07234ec6-4f0a-4653-87c2-b5549b466e3a
- **更新时间**：2025-06-05 04:15:03

---

**【问题级别】**

严重

**【描述】**

将未经验证的用户输入写入日志文件可致使攻击者伪造日志条目或将恶意信息内容注入日志。

**【正确示例】**

```
def verify(data):
    if data == 'safe':
        return data.replace('
', '_').replace('\r', '_')
    else:
        ...

def bad_case():
    a = input()
    a_verify = verify(a)
    syslog.syslog(a_verify)

```
**【错误示例】**

```
import syslog
def bad_case():
    a = input()
    syslog.syslog(a)

```
**【修复建议】**

传入外部数据之前需要对其进行校验
