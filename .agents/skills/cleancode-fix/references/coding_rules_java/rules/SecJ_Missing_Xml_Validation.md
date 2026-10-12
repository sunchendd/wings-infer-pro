# SecJ_Missing_Xml_Validation

- **规则ID**：88d11134-e6bd-4c7f-a266-1492c62d59c7
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

不经过 DTD 或 XML schema 的校验，就直接接受 XML 文档，这样一来，程序员就会为攻击者打开了一扇大门，可以向程序提供无法预测、不合理或是恶意的输入。

**【正确示例】**

```
```java

// 场景一

public void good1() throws Exception {

DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();

factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);

/* 【GOOD】: 创建 XML 解析器或解析器代理，启用校验功能。 */

factory.setFeature("http://xml.org/sax/features/validation", true);

}

// 场景二

public void good2() throws Exception {

DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();

factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);

/* 【GOOD】: 创建 XML 解析器或解析器代理，启用校验功能。 */

factory.setValidating(true);

}

```

```
**【错误示例】**

```
```java

// 场景一

public void bad1() throws Exception {

DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();

factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);

/* 【不符合】: 创建 XML 解析器或解析器代理，未启用校验功能。 */

factory.setFeature("http://xml.org/sax/features/validation", false);

}

// 场景二

public void bad2() throws Exception {

DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();

factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);

/* 【不符合】: 创建 XML 解析器或解析器代理，未启用校验功能。 */

factory.setValidating(false);

}

// 场景三

public void bad3() throws Exception {

DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();

/* 【不符合】: 创建 XML 解析器或解析器代理，未启用校验功能。 */

factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);

}

```

```
**【修复建议】**

解析 XML 时，需要启用验证功能。
