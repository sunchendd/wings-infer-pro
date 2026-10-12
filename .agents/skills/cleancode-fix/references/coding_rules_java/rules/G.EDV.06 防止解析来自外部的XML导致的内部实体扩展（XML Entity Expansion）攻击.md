# G.EDV.06 防止解析来自外部的XML导致的内部实体扩展（XML Entity Expansion）攻击

- **规则ID**：eed1e38d-f321-4023-84b6-9e4087f64ca1
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

由于在解析XML时，`JAXB Unmarshaller` 并且不支持任何用于禁用XXE的标志，因此必须首先通过可配置的安全解析器解析不受信任的XML，从而生成源对象，并将源对象传递给Unmarshaller。例如：javax.xml.bind.Unmarshaller。



`javax.xml.xpath.XPathExpression` XPathExpression不能单独安全地配置，因此必须首先通过另一个安全的XML解析器解析不受信任的数据。

**【正确示例】**

```
##### 场景1：`JAXB Unmarshaller`解析导致XXE问题（`javax.xml.bind.Unmarshaller`）。
- 修复示例1：利用`SAXParserFactory`做安全配置`javax.xml.parsers.SAXParserFactory`：
```java
SAXParserFactory saxParserFactory = SAXParserFactory.newInstance();

// 【GOOD】先通过安全的XML解析器解析不受信任的数据。禁止DTD(doctypes)，禁止DTD(doctypes)
saxParserFactory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
saxParserFactory.setFeature("http://xml.org/sax/features/external-general-entities", false);
saxParserFactory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);

// 做unmarshall操作
Source xmlSource = new SAXSource(saxParserFactory.newSAXParser().getXMLReader(), new InputSource(new StringReader(xmlFile)));
JAXBContext jaxbContext = JAXBContext.newInstance(Object.class);
Unmarshaller unmarshaller = jaxbContext.createUnmarshaller();
unmarshaller.unmarshal(xmlSource);
```
- 修复示例2：利用`XMLReader`做安全配置`org.xml.sax.XMLReader`：
```java
XMLReader xmlreader = XMLReaderFactory.createXMLReader();

// 【GOOD】先通过安全的XML解析器解析不受信任的数据。禁止DTD(doctypes)
xmlreader.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);

// 做unmarshall操作
Source xmlSource = new SAXSource(xmlreader, new InputSource(new StringReader(xmlFile)));
JAXBContext jaxbContext = JAXBContext.newInstance(Object.class);
Unmarshaller unmarshaller = jaxbContext.createUnmarshaller();
unmarshaller.unmarshal(xmlSource);
```
##### 场景2：`XPathExpression`解析导致XXE问题（`javax.xml.xpath.XPathExpression`）。
- 修复示例：利用`DocumentBuilderFactory`做安全配置`javax.xml.parsers.DocumentBuilderFactory`：
```java
DocumentBuilderFactory documentBuilderFactory = DocumentBuilderFactory.newInstance();

// 【GOOD】先通过安全的XML解析器解析不受信任的数据。
documentBuilderFactory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
documentBuilderFactory.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");

DocumentBuilder documentBuilder = documentBuilderFactory.newDocumentBuilder();

// 使用XPathExpression。
String result = new XPathExpression().evaluate(documentBuilder.parse(new ByteArrayInputStream(xmlFile.getBytes())));
```


```
**【错误示例】**

```
##### 场景1：`JAXB Unmarshaller`解析导致XXE问题（`javax.xml.bind.Unmarshaller`）。
- 错误示例：
```java
SAXParserFactory saxParserFactory = SAXParserFactory.newInstance();

// 【不符合】直接做unmarshall操作，不安全。
Source xmlSource = new SAXSource(saxParserFactory.newSAXParser().getXMLReader(), new InputSource(new StringReader(xmlFile)));
JAXBContext jaxbContext = JAXBContext.newInstance(Object.class);
Unmarshaller unmarshaller = jaxbContext.createUnmarshaller();
unmarshaller.unmarshal(xmlSource);
```
##### 场景2：`XPathExpression`解析导致XXE问题（`javax.xml.xpath.XPathExpression`）。
- 错误示例：
```java
DocumentBuilderFactory documentBuilderFactory = DocumentBuilderFactory.newInstance();
DocumentBuilder documentBuilder = documentBuilderFactory.newDocumentBuilder();

// 【不符合】直接进行XPathExpression操作，不安全。
String result = new XPathExpression().evaluate(documentBuilder.parse(new ByteArrayInputStream(xmlFile.getBytes())));
```


```
**【修复建议】**

1. `JAXB Unmarshaller`首先通过可配置的安全解析器解析不受信任的XML，从而生成源对象，并将源对象传递给Unmarshaller。

2. `XPathExpression`首先通过另一个安全的XML解析器解析不受信任的数据。
