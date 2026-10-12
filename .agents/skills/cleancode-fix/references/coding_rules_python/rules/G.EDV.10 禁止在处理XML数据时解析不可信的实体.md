# G.EDV.10 禁止在处理XML数据时解析不可信的实体

- **规则ID**：460b7a59-6c1c-4c39-b18f-6f2071e1c40f
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

本条规则参考自CWE-611：XXE漏洞和CWE-776：XEE漏洞。

XML实体包括内部实体和外部实体。外部实体格式： <!ENTITY 实体名 SYSTEM "URI"\> 或者 <!ENTITY 实体名 PUBLIC "public_ID" "URI"\>。

XXE（XML External Entity）漏洞全称为XML外部实体漏洞，XML文档中可能包含带有URI的外部实体，解析该文档时可通过URI访问其指向的内容，若XML文档中的URI可控，则攻击者可以修改URI指向特定的恶意文件，执行拒绝服务攻击，或未经授权访问系统文件。



XML内部实体格式： <!ENTITY 实体名 "实体的值"\> 。XEE（XML Entity Expansion）漏洞全称为XML实体扩展漏洞，又称十亿狂笑（Billion Laughs）或XML炸弹（XML Bomb），若在处理XML数据时允许使用DTD功能定义XML文档结构，且构造该文档结构的数据可控，则攻击者可在XML文档中构造存在大量嵌套或递归结构的实体，导致解析该文档时数据爆炸性增长，从而造成拒绝服务。因此，在处理XML数据时必须关闭外部实体解析开关，若无法避免解析外部实体，则需对外部实体进行严格校验和净化；此外，建议使用defusedxml模块处理XML数据，详情可参考defusedxml官方文档。

**【正确示例】**

```
# 将resolve_entities参数设置为False或使用defusedxml模块
from lxml import etree


xml_str = ''
with open('xml_file.xml', 'r') as fp:
    xml_str = fp.read()

# 将resolve_entities参数设置为False
parserSafe = etree.XMLParser(resolve_entities=False)
root = etree.XML(xml_str.encode('utf-8'), parser=parserSafe)
_config = list()
for GuestOSType_node in root.getchildren():
    one_guestos = {}
    for item in GuestOSType_node.items():
        one_guestos["@" + item[0]] = item[1]
    for node in GuestOSType_node.getchildren():
        one_guestos[node.tag] = node.text
    _config.append(one_guestos)
print(_config)

# 若无法避免在XML中解析实体，则必须对外部实体进行严格校验和净化。

```
**【错误示例】**

```
【反例1】以下代码存在XXE漏洞
# 假设存在用户可配置的XML文件（xml_file.xml）如下：
# <OSCONFIG version="v001">
#     <GuestOSType id="1" name="CentOS 7.4" OSType="linux" OSbit="64">
#         <MaxCPU>96</MaxCPU>
#         <MaxMemory>128</MaxMemory>
#     </GuestOSType>
# </OSCONFIG>

# 解析该XML文件代码如下
from lxml import etree


xml_str = ''
with open('xml_file.xml', 'r') as fp:
    xml_str = fp.read()

root = etree.XML(xml_str.encode('utf-8'))
_config = list()
for GuestOSType_node in root.getchildren():
    one_guestos = {}
    for item in GuestOSType_node.items():
        one_guestos["@" + item[0]] = item[1]
    for node in GuestOSType_node.getchildren():
        one_guestos[node.tag] = node.text
    _config.append(one_guestos)
print(_config)

# 若攻击者将XML文件（xml_file.xml）内容改为：
# <?xml version="1.0" encoding="utf-8"?>
# <!DOCTYPE title [
#     <!ELEMENT title ANY>
#     <!ENTITY xxe SYSTEM "file:///d:/abc.txt">
# ]>
# <OSCONFIG version="v001">
#     <GuestOSType id="1" name="CentOS 7.4" OSType="linux" OSbit="64">
#         <MaxCPU>96</MaxCPU>
#         <MaxMemory>&xxe;</MaxMemory>
#     </GuestOSType>
# </OSCONFIG>

# 则输入为：
# [{'@id': '1', '@name': 'CentOS 7.4', '@OSType': 'linux', '@OSbit': '64','MaxCPU': '96', 'MaxMemory': 'aaaaa
bbbbb'}]

# “aaaaa
bbbbb”为D盘下abc.txt文件中的内容，此时系统文件已被未授权访问。

【反例2】以下代码存在XEE漏洞
import xml.dom.minidom as dom


xml_path = input()
result = dom.parse(xml_path)
print(result)

# 攻击者可构造恶意XML文件并将路径传入程序：
# <?xml version="1.0"?>
# <!DOCTYPE xee_demo [
#       <!ENTITY xee "xee">
#       <!ENTITY xee2 "&xee;&xee;&xee;&xee;&xee;&xee;&xee;&xee;&xee;&xee;">
#       <!ENTITY xee3 "&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;&xee2;">
#       <!ENTITY xee4 "&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;&xee3;">
#       <!ENTITY xee5 "&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;&xee4;">
#       <!ENTITY xee6 "&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;&xee5;">
#       <!ENTITY xee7 "&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;&xee6;">
#       <!ENTITY xee8 "&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;&xee7;">
#       <!ENTITY xee9 "&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;&xee8;">
# ]>
# <xee_demo>&xee9;</xee_demo>

# 此时解析的XML数据大小将超过3G，若继续增加嵌套数量，则可能用尽内存，导致拒绝服务。

```
**【修复建议】**
