# G.EDV.09 禁止直接使用外部数据作为反射操作中的类名/方法名

- **规则ID**：c711c418-609a-42dd-bc47-7135063a7c0f
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

外部数据的定义请参考**【编程规范】**：外部数据的范围包括但不限于：网络、用户输入（包括命令行、界面）、命令行、文件（包括程序的配置文件）、环境变量、进程间通信（包括管道、消息、共享内存、socket等、RPC）、跨信任域方法参数（对于API）等。



反射操作中直接使用外部数据作为类名或方法名，会导致系统执行非预期的逻辑流程（Unsafe Reflection）。这可被恶意用户利用来绕过安全检查或执行任意代码。当反射操作需要使用外部数据时，必须对外部数据进行白名单校验，明确允许访问的类或方法列表；另外也可以通过让用户在指定范围内选择的方式进行防护。

**【正确示例】**

```
##### 场景1：
- 修复示例1：对外部数据进行白名单校验
```java
String classIndex = request.getParameter("classIndex");
if (whiteList.contains(classIndex)) {
    Class objClass = Class.forName(className);
    BaseClass obj = (BaseClass) objClass.newInstance();
    obj.doSomething();
} else {
    throw new IllegalStateException("Invalid reflect class!");
}
...
```
- 修复示例2：对外部数据进行自定义方法校验
```java
String classIndex = request.getParameter("classIndex");
if (validData(classIndex)) {
    Class objClass = Class.forName(classIndex);
    BaseClass obj = (BaseClass) objClass.newInstance();
    obj.doSomething();
} else {
    throw new IllegalStateException("Invalid reflect class!");
}
...

private boolean validData(String data) {
    // 自定义校验规则，建议使用白名单或正则校验外部数据
}
```

```
**【错误示例】**

```
##### 场景1：
- 错误示例：直接使用外部指定的类名通过反射构造了一个对象

```java
String className = request.getParameter("class");
...
Class objClass = Class.forName(className);
BaseClass obj = (BaseClass) objClass.newInstance();
obj.doSomething();
```

```
**【修复建议】**

避免将外部数据直接用作反射操作的数据源：创建一个规定用户使用的合法名称列表，并仅允许用户从中进行选择。

如果必须使用外部数据用作反射操作的数据源，必须对外部数据进行白名单校验，明确允许访问的类或方法列表。
