# SecPy_VF_Log_Forging_Debug

- **规则ID**：a9351879-9088-454b-a3b9-9bc01186b70c
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
        pass


def good_case():
    a = sys.argv[1]
    a_verify = verify(a)
    logging.debug(a_verify)
    subprocess.getstatusoutput()

```
**【错误示例】**

```
import WebKit
def bad_case():
    a = input()
    # POTENTIAL FLAW:Cross Site Scripting
    b = WebKit.HTTPContent.HTTPContent.writeln(a)

```
**【修复建议】**

传入外部数据之前需要对其进行校验
