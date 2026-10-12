# SecPy_VF_Mail_Command_Injection

- **规则ID**：8bdfd5e7-b799-459d-8f52-b18d73c541f2
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

邮件命令行注入，用户输入的字符串被直接作为SMTP邮件服务器的命令在命令行执行。通过执行SMTP命令，攻击者能够指示服务器执行恶意操作，例如获取敏感信息、发送钓鱼邮件等。

**【正确示例】**

```
```
import smtplib
import re


def verify(data):
    data = data.replace(' ', '').replace('
', '').replace('\r', '').replace('0x0a', '').replace('0x0d', '').replace(
        '0x20', '')
    # 检测逻辑自定义，建议使用白名单校验，如：
    if re.match(r'^[a-zA-Z0-9_]+$', data):
        return data


def good_case():
    cmd = input()
    cmd_verify = verify(cmd)
    session = smtplib.SMTP(smtp_server, smtp_tls_port)
    session.ehlo()
    session.starttls()
    session.login(username, password)
    session.docmd("VRFY", cmd_verify)
```

```
**【错误示例】**

```
```
import smtplib


def bad_case():
    cmd = input()
    session = smtplib.SMTP(smtp_server, smtp_tls_port)
    session.ehlo()
    session.starttls()
    session.login(username, password)
    session.docmd("VRFY", cmd)
```

```
**【修复建议】**

不允许用户直接控制SMTP命令。如果必须允许则需对用户输入通过白名单的方式校验，仅允许输入指定字符。
