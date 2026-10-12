# SecJ_Missing_Xml_Validation_Untyped_Response

- **规则ID**：127aef20-5b8c-477b-bcfa-0504c32f6a51
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

不经过 DTD 或 XML schema 的校验，就直接接受 XML 文档，这样一来，程序员就会为攻击者打开了一扇大门，可以向程序提供无法预测、不合理或是恶意的输入。



本用例用于检查是否对XML 返回类型进行了校验。

**【正确示例】**

```
```java

public void good(QName qName) throws Exception {

Service service = new Service();

Call call = (Call) service.createCall();

/* 【GOOD】: 创建 XML 解析器或解析器代理，启用校验返回值功能。 */

call.setReturnType(qName);

call.invoke();

}

```

```
**【错误示例】**

```
```java

public void bad() throws Exception {

Service service = new Service();

Call call = (Call) service.createCall();

/* 【不符合】: 创建 XML 解析器或解析器代理，未启用校验功能。 */

call.invoke();

}

```

```
**【修复建议】**

创建 XML 解析器或解析器代理时，使用setReturnType启用校验返回值功能
