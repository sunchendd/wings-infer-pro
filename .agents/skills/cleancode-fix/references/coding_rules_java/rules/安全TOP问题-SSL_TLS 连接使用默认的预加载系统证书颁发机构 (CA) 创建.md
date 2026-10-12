# 安全TOP问题-SSL/TLS 连接使用默认的预加载系统证书颁发机构 (CA) 创建

- **规则ID**：5ba35792-6d78-42e1-858d-6c7101a7329f
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

getAcceptedIssuers函数是Java中用于获取SSL证书中可接受的颁发者列表的方法。它可以帮助客户端判断服务器证书的可信度，从而确保SSL通信的安全性。在实际应用中，getAcceptedIssuers方法常用于自定义SSL证书验证，以确保SSL通信的安全性。该方法返回一个X509Certificate数组，其中包含了所有可接受的颁发者的证书。客户端可以通过比对服务器证书中的颁发者信息和本地可接受的颁发者列表，来判断服务器证书的可信度  。自定义实现X509TrustManager接口时getAcceptedIssuers方法不能为空，若为空则存在中间人攻击风险

**【正确示例】**

```
```java

public class MyTrustManagerGood implements X509TrustManager {

@Override

public X509Certificate[] getAcceptedIssuers() {

// 【GOOD】 返回特定的预加载系统证书

return new X509Certificate[0];

}



@Override

public void checkClientTrusted(X509Certificate[] chain, String authType)

throws java.security.cert.CertificateException {

}



@Override

public void checkServerTrusted(X509Certificate[] chain, String authType)

throws java.security.cert.CertificateException {

}

}

```

```
**【错误示例】**

```
```java

public class MyTrustManagerBad implements X509TrustManager {

@Override

public X509Certificate[] getAcceptedIssuers() {

// 【不符合】: 继承javax.net.ssl.X509TrustManager类的getAcceptedIssuers方法的返回值为null。

return null;

}



@Override

public void checkClientTrusted(X509Certificate[] chain, String authType)

throws java.security.cert.CertificateException {

}



@Override

public void checkServerTrusted(X509Certificate[] chain, String authType)

throws java.security.cert.CertificateException {

}

}

```

```
**【修复建议】**

getAcceptedIssuers方法中不要返回空，要返回特定的预加载系统证书
