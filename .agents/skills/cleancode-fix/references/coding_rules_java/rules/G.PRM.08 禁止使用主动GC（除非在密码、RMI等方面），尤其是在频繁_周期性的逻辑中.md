# G.PRM.08 禁止使用主动GC（除非在密码、RMI等方面），尤其是在频繁/周期性的逻辑中

- **规则ID**：726b66b9-33a9-43d7-9bc8-9f2df1da0804
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

严重

**【描述】**

虽然主动调用GC方法时JVM规范不承诺立即进行垃圾回收操作，但是Oracle Java SE JVM在绝大多数情况下响应此方法调用，会触发JVM的全量GC操作，这会增加GC的次数，也就增加了程序因为GC而停顿的时间；而且在GC过程中的某些阶段程序会完全停顿，这会让程序失去响应，对系统造成非常大的风险。在频率/周期性的逻辑（for循环、定时器）中更要尽量避免主动GC的调用。

**【正确示例】**

```
##### 场景1：
- 修复示例：不主动调用GC操作

  ```java
  for (String bookName : bookNames) {
      Book book = new Book(bookName);
      checkBook(book);
      ... // 其他操作
  }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：在循环中调用了`System.gc()`

  ```java
  for (String bookName : bookNames) {
      Book book = new Book(bookName);
      checkBook(book);
      ... // 其他操作
      System.gc();
  }
  ```


```
**【修复建议】**

避免主动执行GC操作，尤其是不能在循环中频繁调用GC操作。
