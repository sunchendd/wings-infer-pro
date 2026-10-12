# SecPy_VF_XSLT_Injection

- **规则ID**：ef28670a-2357-4f42-9b85-1e06f810a37f
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

XSLT是一种用于将XML文档转换为其他格式的语言，例如HTML或XML。XSLT注入发生在应用程序未正确验证或过滤用户提供的输入时，攻击者可以通过在XSLT转换过程中插入恶意代码来执行任意操作。攻击者可以利用XSLT注入来执行各种恶意行为，包括读取敏感数据、修改数据、执行远程命令等。

**【正确示例】**

```
```
from lxml import etree


def good_case():
    # 将resolve_entities参数设置为False
    parser = etree.XMLParser(resolve_entities=False)
    xml = input()
    xml_verify = verify(xml)
    xslt_root = etree.XML(xml_verify, parser)
    transform = etree.XSLT(xslt_root)
    result = transform(xslt_root)
    print(result.getroot().text)


def verify(data):
    # 校验逻辑可自定义
    return data
```

```
**【错误示例】**

```
```
from lxml import etree


def bad_case():
    xml = input()
    xslt_root = etree.XML(xml)
    transform = etree.XSLT(xslt_root)
    result = transform(xslt_root)
    """
    攻击者可构造恶意XLS文件并传入程序：
    <!DOCTYPE dtd_sample[<!ENTITY ext_file SYSTEM "file:///etc/passwd">]>
    <xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">  
      <xsl:template match="/"> 
        <Msg> &ext_file;
      </Msg>
      </xsl:template> 
    </xsl:stylesheet>
    此时将会读取/etc/passwd文件。
    """
```

```
**【修复建议】**

1）避免使用外部数据来动态构造XSLT模板；

2）如果需要使用外部数据来动态构造XSLT模板时，应该对外部数据进行白名单校验，仅允许使用无风险的白名单字符。
