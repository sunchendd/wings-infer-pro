# G.EDV.04 禁止直接使用外部数据来拼接XML

- **规则ID**：93c90824-b464-460a-b417-a19ef38635af
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

直接使用外部数据来构造XML，恶意用户可以向XML中注入额外的节点、节点属性，也可以通过注释对XML格式进行删减、恶意篡改等。

**【正确示例】**

```
##### 场景1：对象是外部用户可控，字段被恶意设置。
- 修复示例1：白名单校验
```java
private static final Pattern INPUT_VALIDATER = Pattern.compile("[\\w\\d]+"); // 【GOOD】利用正则匹配对数据做白名单处理。

public String buildXmlStr(User user) {
    if (INPUT_VALIDATER.matches(user.getUserId()) && INPUT_VALIDATER.matches(user.getDescription())) {
        return "<user><role>operator</role><id>" + user.getUserId() + "</id><description>" + user.getDescription()
            + "</description></user>";
    }
}
```
- 修复示例2：转义
```java
public String buildXmlStr(User user) {
    String encodeUserId = HWEncoder.encodeForXML(user.getUserId()); // 【GOOD】对数据进行编码转义。
    String encodeDec = HWEncoder.encodeForXML(user.getDescription()); // 【GOOD】对数据进行编码转义。
    return "<user><role>operator</role><id>" + encodeUserId + "</id><description>" + encodeDec
        + "</description></user>";
    
}
```
- 修复示例3：使用自定义校验函数去校验外部数据。
```java
public String buildXmlStr(User user) {
    String xmlString = "<user><role>operator</role><id>" + user.getUserId() + "</id><description>"
        + user.getDescription() + "</description></user>";
	...
    if (!validXml(xmlString)) { // validXml 校验函数，校验 xmlString
        return;
    }
    return xmlString;
}
```
- 修复示例4：@Value注入的数据，使用自定义校验函数去校验外部数据。
```java
@Valid
@Value(${com.huawei.config.xml})
private String xml;

public String buildXmlStr() {
    String xmlString = xml;
	...
    if (!validXml(xmlString)) { // validXml 校验函数，校验 xmlString
        return;
    }
    return xmlString;
}
```

```
**【错误示例】**

```
##### 场景1：对象是外部用户可控，字段被恶意设置。
- 错误示例：

```java
// 【不符合】如果User对象是外部用户可控的，最终构造的XML可被恶意篡改
public String buildXmlStr(User user) {
    String xmlString = "<user><role>operator</role><id>" + user.getUserId() + "</id><description>"
        + user.getDescription() + "</description></user>";
	...
    return xmlString;
}
```

```
**【修复建议】**

依据产品业务场景，对外部数据进行校验或转义处理。
