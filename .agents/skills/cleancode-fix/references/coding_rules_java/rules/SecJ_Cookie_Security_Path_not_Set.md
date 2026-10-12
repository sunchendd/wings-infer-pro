# SecJ_Cookie_Security_Path_not_Set

- **规则ID**：f56c6ab8-8bdf-4831-af7b-d015792f927e
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

Path（路径）用于设置可以读取一个cookie的最顶层的目录。如果要限定只有/service/test/目录及其子目录下的页面可以访问该cookie，要把cookies的path属性设置成“/service/test/”，如果不正确的设置，会导致这个cookie的作用域过大。



- 用户可以根据业务需要设置PATH范围，如果业务需要也可以设置为根目录。



- 当前规则关注会话cookie和存储敏感信息cookie是否设置了path，如果是其他cookie可以根据需要选择修改或屏蔽。

**【正确示例】**

```
```java

public void good(ServletRequest request, ServletResponse response, FilterChain chain, String cookieName, String cookieValue)

throws IOException, ServletException {

if (null == chain) {

return;

}

HttpServletResponse httpResponse = (HttpServletResponse) response;

try {

Cookie cookie = new Cookie(cookieName, cookieValue);

// 【GOOD】: cookie 设置了Path参数

cookie.setPath("/service/test/");

httpResponse.addCookie(cookie);

} catch (Exception e) {

... // 处理异常

}

chain.doFilter(request, httpResponse);

}

```

```
**【错误示例】**

```
```java

import javax.servlet.http.Cookie;

import javax.servlet.http.HttpServletResponse;



public void bad(ServletRequest request, ServletResponse response, FilterChain chain, String cookieName, String cookieValue)

throws IOException, ServletException {

if (null == chain) {

return;

}

HttpServletResponse httpResponse = (HttpServletResponse) response;

try {

Cookie cookie = new Cookie(cookieName, cookieValue);

// 【不符合】: cookie未设置path参数会导致cookie域范围过大

cookie.setPath("/");

httpResponse.addCookie(cookie);

} catch (Exception e) {

... // 处理异常

}

chain.doFilter(request, httpResponse);

}

```

```
**【修复建议】**

创建一个javax.servlet.http.Cookie对象,使用setPath()方法设置cookie的path
