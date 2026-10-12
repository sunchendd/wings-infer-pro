# SecPy_VF_XPath_Injection

- **规则ID**：4bc75244-b3b1-4704-ae53-6a560bf887b1
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

XPath注入是一种针对使用XPath语言的应用程序的攻击技术。XPath是一种用于在XML文档中定位和选择节点的查询语言。在应用程序中，如果未正确验证和过滤用户提供的输入，攻击者可以通过在XPath查询中插入恶意代码来执行未经授权的操作。

攻击者可以利用XPath注入来绕过应用程序的身份验证、访问敏感数据、修改查询结果等。攻击者通常会尝试通过构造恶意的XPath查询来利用应用程序的漏洞，例如在输入中插入特殊字符、布尔逻辑运算符或函数调用等。

**【正确示例】**

```
```
from lxml import etree


def good_case():
    xml = '<students><student><id>admin</id><password>123456</password></student></students>'
    tree = etree.XML(xml)
    username = input('请输入用户名：')
    password = input('请输入密码：')
    query = '/students/student[id/text()=$username and password/text()=$password]'
    # 使用预编译查询
    out = tree.xpath(query, username=username, password=password)
    if out:
        print('登录成功，欢迎您' + out[0][0].text)
```

```
**【错误示例】**

```
```
from lxml import etree


def bad_case():
    xml = '<students><student><id>admin</id><password>123456</password></student></students>'
    tree = etree.XML(xml)
    username = input('请输入用户名：')
    password = input('请输入密码：')
    query = '/students/student[id/text()="' + username + '" and password/text()=' + password + ']'
    out = tree.xpath(query)
    if out:
        print('登录成功，欢迎您' + out[0][0].text)
```

```
**【修复建议】**

为了防止XPath注入攻击，应该对用户输入进行严格的验证和过滤，确保只有合法的查询被执行，并使用参数化查询或预编译查询等安全的查询方法。
