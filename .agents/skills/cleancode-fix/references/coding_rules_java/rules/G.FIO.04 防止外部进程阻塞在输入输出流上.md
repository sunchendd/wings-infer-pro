# G.FIO.04 防止外部进程阻塞在输入输出流上

- **规则ID**：92afbb04-4f96-4ffe-8535-9ac3a75a00b2
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

执行Process.waitFor()、exitValue()操作之前要处理输入流和错误流

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

在运行一个外部进程时，如果此进程往其输出流发送任何数据，则必须将其

输出流清空。类似的，如果进程会往其错误流发送数据，其错误流也必须被清空。
