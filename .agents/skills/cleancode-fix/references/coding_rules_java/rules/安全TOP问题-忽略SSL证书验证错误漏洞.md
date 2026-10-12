# 安全TOP问题-忽略SSL证书验证错误漏洞

- **规则ID**：b99030de-95ae-46b8-a07b-9e7619b9682c
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

浏览器能够验证证书的合法性，因此使用权威证书颁发机构颁发的SSL服务器端证书，且证书未过期、没有被撤销、和域名匹配，能够帮助用户确认当前所访问的网站是否合法。备注：由于开发阶段往往无法确认部署时的域名和有效期，所以只能使用开发人员临时生成SSL证书，需要在用户资料中要求客户从权威证书颁发机构购买正式的SSL证书，替换临时SSL证书，并提供相应的实施指导。

**【正确示例】**

```
##### 场景1：
- 修复示例：

```java
private class MyHostnameVerifierGood implements HostnameVerifier {
    public boolean verify(String hostname, SSLSession session) {
        // 【GOOD】 verify方法根据实际使用进行了逻辑验证
        if ("huawei".equals(hostname)) {
            return false;
        }
        return true;
    }
}
```
##### 场景2：
- 修复示例：

```java
public static class MyX509TrustManager implements X509TrustManager {
    private static final String TRUSTED_CERT_ISSUER = "CN=HWIT Enterprise CA 1,CN=kube-ca";
    // 【GOOD】 校验了MyX509TrustManager的证书
    @Override
    public void checkServerTrusted(X509Certificate[] x509Certificates, String str) throws CertificateException {
        for (X509Certificate certificate : x509Certificates) {
            if (!TRUSTED_CERT_ISSUER.contains(certificate.getIssuerDN().getName())) {
            throw new CertificateException("untrusted cert issuer!");
            }
        }
    }
}
```

```
**【错误示例】**

```
##### 场景1：
- 错误示例：

```java
private class MyHostnameVerifierBad implements HostnameVerifier {
    /* 【不符合】: HostnameVerifier继承类的verify方法未做逻辑验证,直接返回了成功。 */
    public boolean verify(String hostname, SSLSession session) {
        /* 不能直接返回true，需要校验hostname */
        return true;
    }
}
```
##### 场景2：
- 错误示例：

```java
public static class DevopsTrustManager implements X509TrustManager, TrustManager {
    /* 【不符合】: X509TrustManager继承类的checkServerTrusted方法未做逻辑验证*/
    @Override public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        /* 需要增加校验逻辑 */
    }
}
```

```
**【修复建议】**

用户可以根据自己业务需要，决定是否需要校验证书，如果不需要校验建议由安全SE或其他资质的角色审核屏蔽。
