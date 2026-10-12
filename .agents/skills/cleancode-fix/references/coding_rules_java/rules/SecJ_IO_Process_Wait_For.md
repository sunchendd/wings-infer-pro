# SecJ_IO_Process_Wait_For

- **规则ID**：95718464-0772-4b40-9016-c18267546482
- **更新时间**：2025-06-05 04:00:03

---

**【问题级别】**

严重

**【描述】**

不正确地处理这些外部程序可能会导致一些意外的异常、

DoS，及其他安全问题。一个进程如果试图从一个空的输入流中读取输入，则会一直阻塞，直到为其提供输入。因

此，在调用这样的进程时，必须为其提供输入。一个外部进程的输出可能会耗尽该进程输出流与错误流的缓冲区。

当发生这种情况时，Java 程序可能会阻塞外部进程，同时阻碍Java程序与外部程序的继续运行。

**【正确示例】**

```
public void testGood() throws InterruptedException, IOException {
    Runtime rt = Runtime.getRuntime();
    Process proc = rt.exec("notemaker");
    StreamGobbler errorGobbler = new StreamGobbler(proc.getErrorStream(), System.err);
    StreamGobbler outputGobbler = new StreamGobbler(proc.getInputStream(), System.out);
    errorGobbler.start();
    outputGobbler.start();
    proc.waitFor();
    // ...
}

```
**【错误示例】**

```
public void testBad() throws Exception {
    Runtime rt = Runtime.getRuntime();
    Process proc = rt.exec("notemaker");
    /* POTENTIAL FLAW: 执行Process.waitFor()、exitValue()操作之前要处理输入流和错误流，如果否则报告警。 */
    proc.waitFor();
    // ...
}

```
**【修复建议】**
