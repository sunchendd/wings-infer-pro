# SecPy_VF_Resource_Injection

- **规则ID**：7b1b6595-ea45-4e63-87a9-9ae924734e1f
- **更新时间**：2025-06-05 04:15:02

---

**【问题级别】**

严重

**【描述】**

检测资源注入，使用用户输入控制资源标识符，借此攻击者可以访问或修改其他受保护的系统资源。覆盖场景与fortify规则 Resource Injection 相同

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
    b = input()
    a_verify = verify(a)
    b_verify = verify(b)
    django.core.mail.EmailMessage.attach(a_verify,b_verify)

```
**【错误示例】**

```
import MiscUtils
import django
def bad_case():
    a = input()
    b = input()
    c = input()
    # POTENTIAL FLAW
    MiscUtils.Configurable.Configurable.setting(a,b,c)
    # POTENTIAL FLAW
    django.core.mail.EmailMessage.attach(a,b)

```
**【修复建议】**

传入外部数据之前需要对其进行校验
