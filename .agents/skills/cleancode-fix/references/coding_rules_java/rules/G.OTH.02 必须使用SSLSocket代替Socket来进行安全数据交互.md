# G.OTH.02 必须使用SSLSocket代替Socket来进行安全数据交互

- **规则ID**：e7d587c6-610f-4a77-99ab-2096a8831efd
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

严重

**【描述】**

只有在与比较陈旧的系统进行通信时，J2EE 标准才允许 use of sockets，因为此时没有较高高级别的协议可用。

**【正确示例】**

```
public void test01Good() throws IOException {
    // Exception handling has been omitted for the sake of brevity
    // ...
    SSLServerSocketFactory sslServerSocketFactory = (SSLServerSocketFactory) SSLServerSocketFactory.getDefault();
    SSLServerSocket sslServerSocket = (SSLServerSocket) sslServerSocketFactory.createServerSocket(9999);
    SSLSocket sslSocket = (SSLSocket) sslServerSocket.accept();
    // ...
}

```
**【错误示例】**

```
public void test01Bad() throws IOException {
    // Exception handling has been omitted for the sake of brevity
    // ...
    /* POTENTIAL FLAW: 检查代码中是否使用了Socket进行通信，如果是则报告警。 */
    ServerSocket serverSocket = new ServerSocket(9999);
    Socket socket = serverSocket.accept();
    // ...
}

```
**【修复建议】**

当网络通信中涉及明文的敏感信息时，需要使用SSLSocket而不是Socket。
