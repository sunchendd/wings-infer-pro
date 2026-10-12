# G.PRM.07 进行IO类操作时，必须在try-with-resource或finally里关闭资源

- **规则ID**：0c0e0b4e-3c53-4cca-89f6-b5b891bb5a92
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

严重

**【描述】**

申请的资源不再使用时，需要及时释放，否则会导致资源泄露问题。释放后的资源不要继续使用，否则可能导致系统抛出异常或其他未知不安全行为。

**【正确示例】**

```
##### 场景1：
- 修复示例1：在finally中释放资源

  ```java
  public void doSomething() {
      FileInputStream in = null;
      try {
          in = new FileInputStream(inputFileName);
      } catch (IOException e) {
          ...
      } finally {
          ...
          in.close();
      }
  }
  ```
- 修复示例2：使用try-with-resource机制，保证资源正确释放

  ```java
  try (FileOutputStream fop = new FileOutputStream(file)) {
      fop.write(buf);
  }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：方法抛出异常时，资源可能无法正确释放

  ```java
  public void doSomething() {
      FileInputStream in = null;
      try {
          in = new FileInputStream(inputFileName);
          in.close();
      } catch (IOException e) {
          int aaaa = 1;
      }
  }
  ```


```
**【修复建议】**

系统异常可能导致资源释放操作被跳过，因此对于IO、数据库操作等需要显式调用关闭方法（如`close()`）来释放资源的场景，必须在try-catch-finally的finally中调用关闭方法。如果有多个资源需要`close()`，需要分别对每个资源`close()`时的异常进行try-catch处理，防止某个资源关闭失败导致其他资源无法正常关闭，最终保证所有资源都能被正确释放。



Java 7有自动资源管理的特性try-with-resource，不需手动关闭。该方式应该优先于try-finally，这样得到的代码将更加简洁、清晰，产生的异常也更有价值。特别是对于多个资源关闭发生异常时，try-finally可能丢失掉前面的异常，而try-with-resource会保留第一个异常，并把后续的异常作为Suppressed exceptions，可通过`getSuppressed()`获取这些异常信息。
