# G.EDV.02 禁止直接使用外部数据构造格式化字符串

- **规则ID**：1dd3cbf3-b798-4ce2-8393-819952100d58
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

外部数据的定义请参考**【编程规范】**：外部数据的范围包括但不限于：网络、用户输入（包括命令行、界面）、命令行、文件（包括程序的配置文件）、环境变量、进程间通信（包括管道、消息、共享内存、socket等、RPC）、跨信任域方法参数（对于API）等。



Java中的Format可以将对象按指定的格式转为某种格式的字符串，格式化字符串可以控制最终字符串的长度、内容、样式，当格式化字符串中指定的格式与格式对象不匹配时还可能会抛出异常。当攻击者可以直接控制格式化字符串时，可能导致多种安全问题：

- 信息泄露：攻击者可能通过构造的格式化字符串获取系统内部信息或敏感数据；

- 拒绝服务（DoS）：恶意构造的字符串可能导致格式化操作失败，从而引发异常，影响系统服务的可用性；

- 功能异常：格式化字符串语法错误可能导致程序行为异常，影响系统正常功能。

**【正确示例】**

```
##### 场景1：格式化字符串类
- 修复示例：使用valid开头的自定义校验函数去校验外部数据。

```java
// 白名单正则，防止重复编译。（仅为示例，请按业务情况自定义）
private static final Pattern VALID_REGEX = Pattern.compile("[0-9a-zA-Z]+");

// valid开头的自定义校验函数。
private boolean validRegex(String key) {
    return (VALID_REGEX.matcher(key).matches()) ? true : false;
}

public void doSomething(HttpServletRequest request) throws WrongInputException {
    String formatStr = req.getParameter("format");
    ...
    String value = getData();

     // 【GOOD】使用valid开头的自定义校验函数去校验外部数据。
    if (validRegex(formatStr)) {
        String.format(formatStr, value));
	...
    } else {
        log.error("Invalid input ...");
        throw new WrongInputException("Invalid input");
	...
    }
}
```

```
**【错误示例】**

```
##### 场景1：格式化字符串类
- 错误示例：对于外部数据直接使用构造格式化字符串，未做合法性校验

```java
public void doSomething() {
    String formatStr = req.getParameter("format");
    ...
    String value = getData();
    
    // 【不符合】 formatStr为外部数据
    String.format(formatStr, value));
}
```

```
**【修复建议】**

1、在实际开发代码过程中，应避免直接使用外部数据构造正则或直接使用外部数据作为正则使用

2、如果确实需要使用的时候，需要对外部数据进行校验过滤，防止外部攻击
