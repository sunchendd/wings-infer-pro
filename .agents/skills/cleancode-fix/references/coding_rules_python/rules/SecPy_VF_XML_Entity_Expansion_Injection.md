# SecPy_VF_XML_Entity_Expansion_Injection

- **规则ID**：94a9d664-2dd5-44b1-a48e-85b1b3cc43c3
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

XML内部实体是实体的内容已经在Doctype中声明。内部实体格式：<!ENTITY 实体名称 "实体的值">。内部实体攻击比较常见的是XML Entity Expansion攻击，又称十亿狂笑（Billion Laughs）或XML炸弹（XML Bomb），若在处理XML数据时允许使用DTD功能定义XML文档结构，且构造该文档结构的数据可控，则攻击者可在XML文档中构造存在大量嵌套或递归结构的实体，导致解析该文档时数据爆炸性增长，从而造成拒绝服务。

**【正确示例】**

```
```
import defusedxml.minidom as dom


def good_case():
    xml_str = input()
    result = dom.parseString(xml_str)
    print(result)
```

```
**【错误示例】**

```
```
import xml.dom.minidom as dom


def bad_case():
    xml_str = input()
    result = dom.parseString(xml_str)
    print(result)
    """
    攻击者可构造恶意XML文件并将路径传入程序：
    
    <?xml version="1.0"?>
    <!DOCTYPE xee_demo [
       <!ENTITY xee "xee">
       <!ENTITY xee2 "&xee;&xee;&xee;&xee;&xee;&xee;&xee;&xee;&xee;&xee;">
       <!ENTITY xee3 "&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;">
       <!ENTITY xee4 "&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;">
       <!ENTITY xee5 "&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;">
       <!ENTITY xee6 "&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;">
       <!ENTITY xee7 "&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;">
       <!ENTITY xee8 "&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;">
       <!ENTITY xee9 "&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;">
    ]>
    <xee_demo>&xee9;</xee_demo>
    此时解析的XML数据大小将超过3G，若继续增加嵌套数量，则可能用尽内存，导致拒绝服务。
    """
```

```
**【修复建议】**

XML文件如设计上不需要引入实体，应禁止解析DTDs；需要引入内部实体，限制实体解析个数，消减解析XML出现内部实体炸弹攻击
