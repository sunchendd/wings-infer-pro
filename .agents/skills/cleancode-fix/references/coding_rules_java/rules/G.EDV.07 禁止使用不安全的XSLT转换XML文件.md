# G.EDV.07 禁止使用不安全的XSLT转换XML文件

- **规则ID**：e280e2bf-5461-4d62-b929-1a16819fd317
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

一般

**【描述】**

XSLT是一种样式转换标记语言，可以将XML数据档转换为另外的XML或其它格式，如HTML网页，纯文字。因为XSLT的功能十分强大，可以导致任意代码执行，当使用TransformerFactory转换XML格式数据的时候，需要添加安全策略禁止不安全的XSLT代码执行。



如果直接使用外部数据来构造XSLT模板，可能导致任意代码执行风险。

**【正确示例】**

```
##### 场景1：
- 修复示例：使用校验函数去校验外部数据。
```java
private void parseContact(){
    /* Initialize data */
    String data = "";

    /* Read data from cookies */
    Cookie cookieSources[] = request.getCookies();
    if (cookieSources != null) {
        data = cookieSources[0].getValue();
    }
	
    if (!validParam(data)) { // 使用valid开头的函数(支持自定义)为校验函数
        return;
    }	
	String xslt = "..." + data + "..."; // 动态构造xslt模板
    TransformerFactory tf = TransformerFactory.newInstance();
	try {
        // 获取转换器对象实例
        Transformer transformer = tf.newTransformer(new StreamSource(xslt));

        // 进行xml数据类型转换
        transformer.transform(new StreamSource(src), new StreamResult(new FileOutputStream(dst)));
    }
}

private boolean validParam(String data) {
    // 下面可以自定义校验方法
    return true;
}
```
- 修复示例2：@Value注入的数据，使用校验函数去校验外部数据。
```java
 @Valid
 @Value(${com.huawei.config.data})
 private String injectData;
 
private void parseContact(){
    /* Initialize data */
    String data =injectData;
    if (!validParam(data)) { // 使用valid开头的函数(支持自定义)为校验函数
        return;
    }	
	String xslt = "..." + data + "..."; // 动态构造xslt模板
    TransformerFactory tf = TransformerFactory.newInstance();
	try {
        // 获取转换器对象实例
        Transformer transformer = tf.newTransformer(new StreamSource(xslt));

        // 进行xml数据类型转换
        transformer.transform(new StreamSource(src), new StreamResult(new FileOutputStream(dst)));
    }
}

private boolean validParam(String data) {
    // 下面可以自定义校验方法
    return true;
}
```

```
**【错误示例】**

```
##### 场景1：
- 错误示例：

```java
private void parseContact(){
    /* Initialize data */
    String data = "";

    /* Read data from cookies */
    Cookie cookieSources[] = request.getCookies();
    if (cookieSources != null) {
        data = cookieSources[0].getValue();
    }	
	String xslt = "..." + data + "..."; // 动态构造xslt模板
    TransformerFactory tf = TransformerFactory.newInstance();
	try {
        // 获取转换器对象实例
        Transformer transformer = tf.newTransformer(new StreamSource(xslt));

        // 进行xml数据类型转换
        transformer.transform(new StreamSource(src), new StreamResult(new FileOutputStream(dst)));
    }
    ...
}
```

```
**【修复建议】**

- 避免使用外部数据来动态构造XSLT模板；

- 如果需要使用外部数据来动态构造XSLT模板时，应该对外部数据进行白名单校验，仅允许使用无风险的白名单字符。
