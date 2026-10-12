# SecJ_Cookie_not_Sent_Over_SSL

- **规则ID**：30ae9f7a-5b68-4387-84bb-b500644dc43a
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

现今的 Web 浏览器支持每个 cookie 的secure标记。如果设置了该标记，那么浏览器只会通过 HTTPS 发送 cookie。通过未加密的通道发送 cookie 将使其受到网络截取攻击，因此安全标记有助于保护 cookie 值的保密性。如果 cookie 包含私人数据或带有会话标识符，那么该标记尤其重要。

**【正确示例】**

```
```java

public Response good() {

Cookie cookie = new Cookie("name", "value");

/* 【GOOD】创建了 cookie，将 secure 标记设置为 TRUE */

NewCookie newCookie = new NewCookie(cookie, "comment", 100, true);

Response.ResponseBuilder builder = Response.ok("hello", "text/plain");

return builder.cookie(newCookie).build();

}

```

```
**【错误示例】**

```
```java

public Response bad() {

Cookie cookie = new Cookie("name", "value");

/* 【不符合】创建了 cookie，但未将 secure 标记设置为 TRUE */

NewCookie newCookie = new NewCookie(cookie, "comment", 100, false);

Response.ResponseBuilder builder = Response.ok("hello", "text/plain");

return builder.cookie(newCookie).build();

}

```

```
**【修复建议】**

创建cookie时，将secure 标记设置为 true。
