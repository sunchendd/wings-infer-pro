# P.05 外部数据使用前必须进行合法性校验

- **规则ID**：ad6ff25d-126c-4b4b-81fb-8ed780cdc83a
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

外部数据的定义请参考**【编程规范】**：外部数据的范围包括但不限于：网络、用户输入（包括命令行、界面）、命令行、文件（包括程序的配置文件）、环境变量、进程间通信（包括管道、消息、共享内存、socket等、RPC）、跨信任域方法参数（对于API）等。

Java语言中EL(Expression Language)框架常用的有JSTL、OGNL、MVEL、SPEL、JEXL等，使用表达式可以实现获取数据、执行运算、获取Java对象、调用Java方法等功能。直接使用外部数据构造表达式时，恶意用户通过精心构造，可以篡改表达式的逻辑，执行任意Java代码，导致系统数据被恶意删除/修改/泄露风险，甚至执行任意系统命令。

**【正确示例】**

```
##### 场景1：SPEL
- 修复示例1：使用间接引用
```java
private static void doSomething() {        
    ...    
    String index = request.getParameter("spelIndex");
    String expression = validData(index); // 将el表达式的代号映射为具体的表达式
    ExpressionParser parser = new SpelExpressionParser();
    Object value = parser.parseExpression(expression).getValue();
}

private String validData(String index ) {
    // 根据业务自定义校验逻辑
    return spelMap.get(index);
}
```
- 修复示例2：使用白名单校验
```java
private static void doSomething() {        
    ...    
    String expression = request.getParameter("spel");
    if (!validData(expression )) {
        throw new IllegalArgumentException("Invalid input");
    }
    ExpressionParser parser = new SpelExpressionParser();
    Object value = parser.parseExpression(expression).getValue();
}

private boolean validData(String expression) {
    // 根据业务自定义校验逻辑，比如白名单校验
    return expression.matches("[\\w\\s+]*");
}
```
- 修复示例3：使用自定义校验函数去校验外部数据。
```java
private static void doSomething() {
    String expression = request.getParameter("spel");
    if (!validData(expression)) { // validData 校验函数，校验 expression
        throw new IllegalArgumentException("Invalid input ...");
    }
    ExpressionParser parser = new SpelExpressionParser();
    Object value = parser.parseExpression(expression).getValue();
}

private boolean validData(String expression) {
    // 根据业务自定义校验逻辑
    ...
}
```

```
**【错误示例】**

```
##### 场景1：SPEL
- 错误示例：直接使用外部数据作用EL表达式

```java
private static void doSomething() {  
    ...    
    String expression = request.getParameter("spel");
    ExpressionParser parser = new SpelExpressionParser();
    Object value = parser.parseExpression(expression).getValue();
}
```

```
**【修复建议】**

避免使用外部数据构造EL表达式，如果需要用户指定表达式，建议采用间接对象引用方式，用户只能选择要使用的表达式代号，在代码中映射为要执行的EL表达式；

如果需要使用外部数据拼接EL表达式，需使用白名单校验方式对外部数据进行校验。
