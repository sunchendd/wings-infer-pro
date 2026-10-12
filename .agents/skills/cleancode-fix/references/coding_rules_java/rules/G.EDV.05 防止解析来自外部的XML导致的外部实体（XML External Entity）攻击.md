# G.EDV.05 防止解析来自外部的XML导致的外部实体（XML External Entity）攻击

- **规则ID**：fe60b2c6-6297-449d-87bc-7dad5f3c2aba
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

严重

**【描述】**

XML Entity Expansion injection 也称为 XML Bombs，属于 DoS 攻击，利用格式工整的有效 XML 块，它们在耗尽服务器分配的资源之前不断呈指数式扩张。XML 允许定义作为字符串替代宏的自定义实体。通过嵌套复发性实体解析，攻击者可以轻松使服务器资源崩溃。

**【正确示例】**

```
public void good() throws Exception {
    // 正确示例-- 完全禁用DTD
    XMLInputFactory xmlFactory = XMLInputFactory.newFactory();
    xmlFactory.setProperty(XMLInputFactory.SUPPORT_DTD, false);
    XMLStreamReader reader = xmlFactory.createXMLStreamReader(new FileInputStream("demo.xml"));
}

```
**【错误示例】**

```
public void bad() throws Exception {
    // 错误示例-- 不禁用DTD
    XMLInputFactory xmlFactory = XMLInputFactory.newFactory();
    /* POTENTIAL FLAW: XML External Entities 攻击可利用能够在处理时动态构建文档的 XML 功能。XML 实体可动态包含来自给定资源的数据。外部实体允许 XML 文档包含来自外部 URI 的数据。除非另行配置，否则外部实体会迫使 XML 解析器访问由 URI 指定的资源，例如位于本地计算机或远程系统上的某个文件。这一行为会将应用程序暴露给 XML External Entity (XXE) 攻击，从而用于拒绝本地系统的服务，获取对本地计算机上文件未经授权的访问权限，扫描远程计算机，并拒绝远程系统的服务。 */
    XMLStreamReader reader = xmlFactory.createXMLStreamReader(new FileInputStream("demo.xml"));
}

```
**【修复建议】**

为了避免 XXE 注入，应对 XML 解析器进行安全配置。
