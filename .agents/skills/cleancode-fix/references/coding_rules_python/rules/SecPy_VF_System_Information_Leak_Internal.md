# SecPy_VF_System_Information_Leak_Internal

- **规则ID**：a37adedf-c400-462a-81fb-51a029a302c7
- **更新时间**：2025-06-05 04:15:02

---

**【问题级别】**

严重

**【描述】**

通过打印或日志记录功能将系统数据或调试信息发送到本地文件、控制台或屏幕时，就会发生内部信息泄露。在某些情况下，错误消息会告诉攻击者系统易遭受的确切攻击类型。例如，数据库错误消息可以揭示应用程序容易受到 SQL Injection 攻击。其他错误消息可以揭示有关该系统的更多间接线索。

**【正确示例】**

```
def verify(data):
    if data == 'safe':
        return data.replace('
', '_').replace('\r', '_')
    else:
        ...

def good_case():
    a = input()
    # POTENTIAL FLAW
    a_verify = verify(a)
    six.print(a_verify)

```
**【错误示例】**

```
import six
def bad():
    a = input()
    # POTENTIAL FLAW
    six.print(a)

```
**【修复建议】**

传入外部数据之前需要对其进行校验
