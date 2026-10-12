# SecPy_VF_XML_External_Entity_Injection

- **规则ID**：76e5e869-ced3-45f7-bf37-8999dc216eb8
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

XML实体注入攻击利用的就是XML解析器能够解析外部或内部资源，获取内容并替换在xml中的能力。在解析外部实体过程中，XML的分析器会使用众多的网络协议和服务（DNS,FTP,HTTP,SMB等），这取决于URLs中指定的协议类型。XML实体注入攻击主要造成以下几种危害：读取本地文件（可能包含敏感信息 /etc/password）、内存侵犯、任意代码执行、拒绝服务

**【正确示例】**

```
```
# 【正例 1】
from lxml import etree


def good_case1():
    xml_str = input()
    # 将resolve_entities参数设置为False
    parser = etree.XMLParser(resolve_entities=False)
    tree = etree.XML(xml_str, parser)
    print(tree.text)


# 【正例 2】
# 使用defusedxml模块
from defusedxml import lxml


def good_case2():
    xml_str = input()
    tree = lxml.XML(xml_str)
    print(tree.text)
```

```
**【错误示例】**

```
```
from lxml import etree


def bad_case():
    xml_str = input()
    tree = etree.XML(xml_str)
    print(tree.text)
    """
    攻击者可构造恶意XML文件并将路径传入程序：
    <!DOCTYPE ent [
    <!ENTITY ent SYSTEM "file:///etc/passwd">
    ]>
    <b>&ent;</b>
    此时解析的XML数据大小将超过3G，若继续增加嵌套数量，则可能用尽内存，导致拒绝服务。
    """
```

```
**【修复建议】**

XML文件如设计上不需要引入实体，应禁止解析DTDs；需要引入内部实体，则应禁止解析外部实体
