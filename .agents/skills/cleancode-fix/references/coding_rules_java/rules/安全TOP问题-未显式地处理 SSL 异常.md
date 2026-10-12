# 安全TOP问题-未显式地处理 SSL 异常

- **规则ID**：4f3268d0-321b-4490-8dd1-4d27fe6ecfb4
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

未处理的 SSL 异常会在以下情况中发生：1）抛出特定的 SSL 异常；2）未显式地处理异常。

特定 SSL 异常 、 和  都可以传达与 SSL 连接相关的重要错误。如果没有显式地处理这些错误，连接会被处于一种意想不到的、潜在不安全的状态。

**【正确示例】**

```
public void test01Good(InputStream inputStream) {
    try {
        unzipAssetsFiles01(inputStream);
    } catch (SSLHandshakeException e) {
        LOGGER.error(e.getMessage());
        // ...
    }
}

private void unzipAssetsFiles01(InputStream inputStream) throws SSLHandshakeException {
    ZipInputStream zipInputStream = new ZipInputStream(inputStream);
    try {
        ZipEntry zipEntry = zipInputStream.getNextEntry();
    } catch (Exception e) {
        throw new SSLHandshakeException(null);
    }
}

```
**【错误示例】**

```
public void test01Bad(InputStream inputStream) throws SSLHandshakeException {
    /* POTENTIAL FLAW: 没有显式地处理 SSL 异常可能会导致应用程序无法发现意外状况和情况。 */
    unzipAssetsFiles01(inputStream);
}

private void unzipAssetsFiles01(InputStream inputStream) throws SSLHandshakeException {
    ZipInputStream zipInputStream = new ZipInputStream(inputStream);
    try {
        ZipEntry zipEntry = zipInputStream.getNextEntry();
    } catch (Exception e) {
        throw new SSLHandshakeException(null);
    }
}

```
**【修复建议】**

对SSL异常进行显式处理。
