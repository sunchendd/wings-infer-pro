# SecS_LDAP_Injection

- **规则ID**：126882fb-7452-4911-a8b7-47869a9881e3
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

LDAP注入是一种针对LDAP（轻量级目录访问协议）服务器的攻击手段，攻击者通过在查询参数中插入恶意代码，以获取敏感信息或执行未经授权的操作。

**【正确示例】**

```
```java

public static boolean validLdapInput(String input) {

// 此处可以使用正则等方式做校验

}

private void goodG2B() throws Throwable {

String data;

data = ""; /* Initialize data */



{

/* Read data from an environment variable */

data = System.getenv("data");

}

// 【GOOD】 使用白名单对外部输入进行校验，具体业务需要实现自己需要的白名单

if (!validLdapInput(data))

{

IO.logger.log(Level.WARNING, "Error validLdapInput");

return;

}



Hashtable<String, String> environmentHashTable = new Hashtable<String, String>();

environmentHashTable.put(Context.INITIAL_CONTEXT_FACTORY, "com.sun.jndi.ldap.LdapCtxFactory");

environmentHashTable.put(Context.PROVIDER_URL, "ldap://localhost:389");

DirContext directoryContext = null;



try {

directoryContext = new InitialDirContext(environmentHashTable);

String search = "(cn=" + data + ")";

// 【GOOD】 输入的data已校验，没有注入风险

NamingEnumeration<SearchResult> answer = directoryContext.search("", search, null);

while (answer.hasMore()) {

SearchResult searchResult = answer.next();

Attributes attributes = searchResult.getAttributes();

NamingEnumeration<?> allAttributes = attributes.getAll();

while (allAttributes.hasMore()) {

Attribute attribute = (Attribute) allAttributes.next();

NamingEnumeration<?> allValues = attribute.getAll();

while (allValues.hasMore()) {

IO.writeLine(" Value: " + allValues.next().toString());

}

}

}

} catch (NamingException exceptNaming) {

IO.logger.log(Level.WARNING, "The LDAP service was not found or login failed.", exceptNaming);

} finally {

if (directoryContext != null) {

try {

directoryContext.close();

} catch (NamingException exceptNaming) {

IO.logger.log(Level.WARNING, "Error closing DirContext", exceptNaming);

}

}

}



}

```

```
**【错误示例】**

```
```java

public void bad() throws Throwable {

String data;

data = ""; /* Initialize data */



{

/* Read data from an environment variable */

data = System.getenv("data");

}



Hashtable<String, String> environmentHashTable = new Hashtable<String, String>();

environmentHashTable.put(Context.INITIAL_CONTEXT_FACTORY, "com.sun.jndi.ldap.LdapCtxFactory");

environmentHashTable.put(Context.PROVIDER_URL, "ldap://localhost:389");

DirContext directoryContext = null;



try {

directoryContext = new InitialDirContext(environmentHashTable);

String search = "(cn=" + data + ")";

/* 【不符合】:LDAP的输入data存在注入风险 */

NamingEnumeration<SearchResult> answer = directoryContext.search("", search, null);

while (answer.hasMore()) {

SearchResult searchResult = answer.next();

Attributes attributes = searchResult.getAttributes();

NamingEnumeration<?> allAttributes = attributes.getAll();

while (allAttributes.hasMore()) {

Attribute attribute = (Attribute) allAttributes.next();

NamingEnumeration<?> allValues = attribute.getAll();

while (allValues.hasMore()) {

IO.writeLine(" Value: " + allValues.next().toString());

}

}

}

} catch (NamingException exceptNaming) {

IO.logger.log(Level.WARNING, "The LDAP service was not found or login failed.", exceptNaming);

} finally {

if (directoryContext != null) {

try {

directoryContext.close();

} catch (NamingException exceptNaming) {

IO.logger.log(Level.WARNING, "Error closing DirContext", exceptNaming);

}

}

}



}

```

```
**【修复建议】**

为了防止LDAP注入，可以采取以下措施：



- 对用户输入进行验证和过滤，确保只接受预期的字符和格式。



- 使用预编译语句和参数化查询，避免将用户输入直接拼接到SQL查询中。



- 对LDAP查询结果进行适当的处理和过滤，避免泄露敏感信息。
