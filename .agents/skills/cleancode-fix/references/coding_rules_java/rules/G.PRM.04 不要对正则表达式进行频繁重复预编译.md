# G.PRM.04 不要对正则表达式进行频繁重复预编译

- **规则ID**：efb9f50f-db9e-4851-8609-d4f4aa2f558b
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

在频繁调用的场景（例如在方法体内或循环语句中）中，定义Pattern会导致重复预编译正则表达式，降低程序执行效率。另外，对于JDK中的某些API会接受字符串格式的正则表达式作为参数，如`String.replaceAll`、`String.split`等，对于这些API的使用也要考虑性能问题。

**【正确示例】**

```
##### 场景1： 方法内定义Pattern，方法频繁被调用时导致正则表达式重复预编译
- 修复示例：将Pattern定义为类属性

  ```java
  public class RegexExp {
      private static final Pattern CHARSET_REG = Pattern.compile("[a-z]+");

      // 该方法被频繁调用
      private boolean isLowerCase(String str) {
          if (CHARSET_REG.matcher(str).find()) {
              return true;
          }
          return false;
      }
  }
  ```
##### 场景2： for循环内定义Pattern，导致正则表达式重复预编译
- 修复示例：将Pattern定义为类属性

  ```java
  public class RegexExp {
      private static final Pattern CHARSET_REG = Pattern.compile("[a-z]+");

      private void doSomething(String[] args) {
          int count = 0;
          for (String str : args) {
              if (CHARSET_REG.matcher(str).find()) {
                  count++;
              }
          }
          ...
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1： 方法内定义Pattern，方法频繁被调用时导致正则表达式重复预编译
- 错误示例：

  ```java
  public class RegexExp {
      // 该方法被频繁调用
      private boolean isLowerCase(String str) {
          Pattern pattern = Pattern.compile("[a-z]+");
          if (pattern.matcher(str).find()) {
              return true;
          }
          return false;
      }
  }
  ```
##### 场景2： for循环内定义Pattern，导致正则表达式重复预编译
- 错误示例：

  ```java
  public class RegexExp {
      private void doSomething(String[] args) {
          int count = 0;
          for (String str : args) {
              Pattern pattern = Pattern.compile("[a-z]+");
              if (pattern.matcher(str).find()) {
                  count++;
              }
          }
          ...
      }
  }
  ```


```
**【修复建议】**

扩大Pattern的作用域，如用类属性的方式，避免正则表达式从重复编译。
