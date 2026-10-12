# G.ERR.11 对于GeneralSecurityException及其子类异常应记录日志

- **规则ID**：c672fe52-2e4e-44b3-9bcc-ee22254a7a90
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

提示

**【描述】**

GeneralSecurityException是一个一般安全异常类，其子类定义了各种跟安全相关的异常，比如加解密操作相关异常、证书验证相关异常。当系统中抛出这些异常时，表示系统中的一些安全相关的功能出现问题或遇到一些非预期的场景。所以对于这些异常建议在日志中进行详细记录，方便后续进行问题分析定位及对系统的安全性进行优化完善。这些异常中如果含有秘钥、口令等敏感信息时，记录日志前应该对这些敏感信息进行过滤。

**【正确示例】**

```
try {
    Signature signature = Signature.getInstance("SHA1withRSA");
} catch (GeneralSecurityException e) {
    LOGGER.error("test");
}
try {
    Signature signature = Signature.getInstance("SHA1withRSA");
} catch (NoSuchAlgorithmException e) {
     LOGGER.warn("test");
}

```
**【错误示例】**

```
try {
    Signature signature = Signature.getInstance("SHA1withRSA");
} catch (GeneralSecurityException e) {
    
}

```
**【修复建议】**

对于GeneralSecurityException及其子类异常应记录日志
