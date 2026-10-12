# G.ERR.01 不要通过一个空的catch块忽略异常

- **规则ID**：7174bd65-78dc-4761-bf26-0b948023f169
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

异常表示程序运行发生了错误，发生异常会中断程序的正常处理流程。不应该使用空的catch块会忽略发生的异常，发生异常要么在catch块中对异常情况进行处理，要么将异常抛出，交由上层调用方进行处理。

**【正确示例】**

```
##### 场景1：代码中应避免空的catch块
- 修复示例： 消除代码中的空catch块
  ```java
  InputStream inputStream = null;
  try {
      inputStream = new InputStream(null);
      doSomething();
  } catch (Exception t) {
      logger.error("something is wrong");
  }    
  ```


```
**【错误示例】**

```
##### 场景1：代码中应避免空的catch块
- 错误示例： 使用空catch块忽略异常
  ```java
  InputStream inputStream = null;
  try {
      inputStream = new InputStream(null);
      doSomething();
  } catch (Exception t) {
  }
  ...
  ```


```
**【修复建议】**

代码中避免出现空的catch块，确实需要空catch块，建议添加注释，解释为什么可以忽略该异常。
