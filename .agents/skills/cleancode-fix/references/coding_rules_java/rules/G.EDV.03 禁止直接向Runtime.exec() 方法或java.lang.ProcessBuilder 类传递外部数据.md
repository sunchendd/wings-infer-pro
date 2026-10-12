# G.EDV.03 禁止直接向Runtime.exec() 方法或java.lang.ProcessBuilder 类传递外部数据

- **规则ID**：55bca84a-d70d-4e53-a928-d5e5d9453f09
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

外部数据的定义请参考**【编程规范】**：外部数据的范围包括但不限于：网络、用户输入（包括命令行、界面）、命令行、文件（包括程序的配置文件）、环境变量、进程间通信（包括管道、消息、共享内存、socket等、RPC）、跨信任域方法参数（对于API）等。

直接使用外部数据构造命令行时，恶意用户可向命令行中注入额外的命令语句（命令注入）或向命名语句中注入额外的参数（参数注入）。

**【正确示例】**

```
##### 场景1：
- 修复示例1：外部数据用于拼接命令行时，可使用白名单方式对外部数据进行校验，保证外部数据中不含注入风险的特殊字符。

```java
// str值来自用户输入
public void doSomething() {
    String data = System.getenv("data");
    String osCommand;
    if (System.getProperty("os.name").toLowerCase().indexOf("win") >= 0) {
        osCommand = "c:\\WINDOWS\\SYSTEM32\\cmd.exe /c dir ";
    } else {
        osCommand = "/bin/ls ";
    }
    Process process = null;
    try {
        // 使用自定义校验方法校验外部输入的数据
        if (!validateData(data)) {
             throw new IllegalArgumentException("...");
        }
        process = Runtime.getRuntime().exec(osCommand + data);
    } catch (IOException e) {
        IO.writeLine(e.getMessage());
    }
    ...
}

private boolean validateData(String data) { // 自定义校验函数
    /* 自定义校验逻辑，建议使用白名单或正则的方式来过滤出正确的数据 */
 }
```
- 修复示例2：对外部数据中存在命令注入风险的特殊字符进行转义

```java
String encodeIp = HWEncoder.encodeForOS(new WindowsCodec(), ip);
String cmd = "cmd.exe /c ping " + encodeIp;
Runtime rt = Runtime.getRuntime();
Process proc = rt.exec(cmd);
...
```



```
**【错误示例】**

```
##### 场景1：
- 错误示例：对于外部数据直接调用exec，未做合法性校验

```java
public void doSomething() {
    String data = System.getenv("data");
    String osCommand;
    if (System.getProperty("os.name").toLowerCase().indexOf("win") >= 0) {
        osCommand = "c:\\WINDOWS\\SYSTEM32\\cmd.exe /c dir ";
    } else {
        osCommand = "/bin/ls ";
    }
    Process process = null;
    try {
        // 【POTENTIAL FLAW】command injection
        process = Runtime.getRuntime().exec(osCommand + data);
        ...
    } catch (IOException e) {
        IO.writeLine(e.getMessage());
    }
    ...
}
```


```
**【修复建议】**

针对命令注入问题，常用的防护措施包括：

- **对外部数据进行校验**：外部数据用于拼接命令行时，可使用白名单方式对外部数据进行校验，保证外部数据中不含注入风险的特殊字符；

- **对外部数据中存在命令注入风险的特殊字符进行转义**：在执行命令行时，如果输入校验不能禁止有风险的特殊字符，需先外部输入进行转义处理，转义后的字段拼接命令行可有效防止命令注入的产生。对于转义的API，推荐使用Huawei WSF安全框架中的API，另外也可以使用业界开源组件esapi中的API。
