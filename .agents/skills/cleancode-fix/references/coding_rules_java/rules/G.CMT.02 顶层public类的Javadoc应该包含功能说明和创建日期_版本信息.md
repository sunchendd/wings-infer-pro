# G.CMT.02 顶层public类的Javadoc应该包含功能说明和创建日期/版本信息

- **规则ID**：3ba71ed6-391a-4674-adc4-0e25764c2abb
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

顶层public类的Javadoc中应该有功能说明、`@since`信息。日期格式为Java 8 time包中的[ISO_DATE](https://docs.oracle.com/javase/8/docs/api/java/time/format/DateTimeFormatter.html#ISO_DATE)，例如“2011-12-03”或者“2011-12-03+01:00”。



编写文件头或顶层类头注释应注意：



- 禁止空有格式，无内容。

- 业界Java源码中一般没有History信息，History在配置库里面可以查询，不建议在Java源码的注释中包含History。

- 顶层public类头中创建日期的`@since`标签中的年份应该与版权中的起始年份相同。

**【正确示例】**

```
##### 场景1：
- 修复示例：

```java
// 【GOOD】添加了顶层class的注释
/**
 * TopClassComment的功能说明
 *
 * @since 2020/5/26
 */
 public enum TopClassComment {
     ...
 }
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：注释中无功能说明、`@since`信息

  ```java
  // 【不符合】注释中无功能说明、`@since`信息
  public enum TopClassComment {
      ...
  }
  ```


```
**【修复建议】**

在Javadoc中添加功能说明、添加@since注解，并在后面添加时间，例如：@since 2023-08-29

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
