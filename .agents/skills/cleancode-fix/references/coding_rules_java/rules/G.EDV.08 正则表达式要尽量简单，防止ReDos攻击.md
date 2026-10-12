# G.EDV.08 正则表达式要尽量简单，防止ReDos攻击

- **规则ID**：603435f9-e6ee-4e0a-bdf9-2430050ce92f
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

ReDos（Regular Expression Denial of Service）攻击是一种针对正则表达式引擎的拒绝服务攻击。攻击者通过构造精心设计的输入字符串，利用正则表达式引擎在处理这些字符串时的资源消耗特性，导致匹配过程异常缓慢或者进入无限循环，从而耗尽服务器的计算资源，影响正常服务的运行。

当正则表达式中含有自我重复的重复分组（`^(\d+)*$`、`^(\d+|\s+)*$`）或替换的重复分组（`^(\d|\d|\d)+$`、`^(\d|\d?)+$`）时，容易发生Redos问题。发生Redos风险的原因是：Java中的正则匹配使用的是NFA引擎，NFA引擎的回溯机制，导致当字符串文本与正则表达式不匹配时，所花费的时间要比匹配时多，即要确定匹配失败，需要与所有可能的路径进行对比匹配，证明都不匹配时，才返回匹配失败。



当使用外部数据构造正则或直接用作正则时，恶意用户可能会向系统中注入存在Redos风险的正则。正确的做法是先验证和清理外部数据，以确保正则的安全性。

**【正确示例】**

```
##### 场景1：
- 修复示例：使用valid开头的自定义校验函数去校验外部数据。

```java
// 白名单正则，防止重复编译。
private static final Pattern VALID_REGEX = Pattern.compile("[0-9a-zA-Z]+");

// valid开头的自定义校验函数。
private boolean validRegex(String key) {
    return (VALID_REGEX.matcher(key).matches()) ? true : false;
}

public void doSomething(HttpServletRequest request) throws WrongInputException {
    String key = request.getParameter("keyword");

    // 【GOOD】使用valid开头的自定义校验函数去校验外部数据（白名单校验）。
    if (validRegex(key)) {
        String regex = "[a-zA-Z0-9_-]+@" + key + "\\.com";
        Pattern searchPattern = Pattern.compile(regex);
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
##### 场景1：
- 错误示例：对于外部数据直接使用正则解析，未做合法性校验

```java
public void doSomething() throws Throwable {
   String key = request.getParameter("keyword");
    ...
    String regex = "[a-zA-Z0-9_-]+@" + key + "\\.com";
    
    // 【不符合】Denial of Service: Regular Expression
    Pattern searchPattern = Pattern.compile(regex);
...
}
```

```
**【修复建议】**

对外部数据使用前进行校验，保证最终构造出来的正则表达式中不存在Redos风险（即保证正则表达式中不存在重复分组）。



对于代码中硬编码的正则表达式，要对正则表达式进行简化，去除正则表达式中的重复分组。例如`Email格式验证`的正则

`^([0-9a-zA-Z]([-.\w]*[0-9a-zA-Z])*@(([0-9a-zA-Z])+([-\w]*[0-9a-zA-Z])*\.)+[a-zA-Z]{2,9})$`中的`(([-\w]*[0-9a-zA-Z])*\.)+`存在redos问题，可以修改为`([-\w]*\.)+`。
