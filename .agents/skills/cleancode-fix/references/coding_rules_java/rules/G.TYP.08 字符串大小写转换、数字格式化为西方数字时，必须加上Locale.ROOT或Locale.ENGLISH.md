# G.TYP.08 字符串大小写转换、数字格式化为西方数字时，必须加上Locale.ROOT或Locale.ENGLISH

- **规则ID**：9756fb31-7368-4760-8226-63568a237d86
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

一般

**【描述】**

字符串大小写转换时要考虑地区语言上的差异。`String`类的`toUpperCase()`、`toLowerCase()`方法、`format()`方法，如果不指定输入参数，则会按当前系统默认的编码模式转换，可能会导致非预期的转换结果。



字符对区域不敏感的，例如协议关键字、HTML的tags等优先用ROOT，字符对区域敏感或者强调英文习惯的应使用ENGLISH。



如果确实需要在本地化GUI显示本地语言数字文字，也允许使用：



- Locale.getDefault(Locale.Category.DISPLAY)

- mystr.getBytes(StandardCharsets.UTF_8)

**【正确示例】**

```
##### 场景1：数字格式化为西方数字场景
- 修复示例1：

  ```java
  String testString = String.format(Locale.ROOT, "%d", 2);
  System.out.println(testString);
  ```
##### 场景2：字符串大小写转换场景
- 修复示例1：

  ```java
  String testString = "i";
  System.out.println(testString.toUpperCase(Locale.ROOT));
  ```


```
**【错误示例】**

```
##### 场景1：数字格式化为西方数字场景
- 错误示例：

  ```java
  String testString = String.format("%d", 2);
  System.out.println(testString); // locale设置为ar-SA，2格式化后输出'  '
  ```
##### 场景2：字符串大小写转换场景
- 错误示例：

  ```java
  String testString = "i";
  System.out.println(testString.toUpperCase());
  ```


```
**【修复建议】**

数字格式化为西方数字或字符串大小写转换时，加上`Locale.ROOT`或`Locale.ENGLISH`；
