# SecPy_VF_Header_Manipulation

- **规则ID**：e98081da-fa93-480b-b69c-4f8d463357cd
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

外部数据直接写入 HTTP 响应头时，恶意用户可通过回车换行符（CRLF）向HTTP响应中注入精心构造的数据，到达注入额外响应头、篡改HTTP响应报文的目的，最终导致cache-poisoning、cross-site scripting、page hijacking、cookie manipulation 或 open redirect 等漏洞。



其中最常见的一种 Header Manipulation 攻击是 HTTP Response Splitting，即通过 CRLF（回车、换行符）控制服务端要发送的响应剩余头和 body 内容，甚至可以创建针对其他请求的完整响应报文。

**【正确示例】**

```
```
from django.http import HttpResponse
import re


def verify(data):
    data = data.replace('
', '').replace('\r', '').replace('0x0a', '').replace('0x0d', '')
    # 检测逻辑自定义，建议使用白名单校验，如：
    if re.match(r'^[a-zA-Z0-9_]+$', data):
        return data


def good_case():
    a = input()
    b = input()
    a_verify = verify(a)
    b_verify = verify(b)
    response = HttpResponse()
    response.set_cookie(a_verify, b_verify)

```

```
**【错误示例】**

```
```
from django.http import HttpResponse


def bad_case():
    a = input()
    b = input()
    response = HttpResponse()
    # 不符合
    response.set_cookie(a, b)

```

```
**【修复建议】**

不允许用户直接控制 HTTP 响应头。如果必须允许则需对用户输入通过白名单的方式校验，仅允许输入指定字符，保证外部数据中不包含 CRLF 等字符。
