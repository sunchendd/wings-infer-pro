# G.FMT.20 数字字面量应该设置合适的后缀，long类型应该使用L作为后缀

- **规则ID**：7707a7da-57db-4e05-b026-863da41b6405
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

`long`值必须使用`L`后缀，不能使用`l`做后缀。例如，使用`500000L`而不是`500000l`。



float、double类型也要添加对应的后缀，d、f后缀不易引起混淆的，不强制采用大写字母。



Java 10增加了局部类型推断LVTI，一些字面量如果不加后缀，类型推断时可能与预期不符。为了形成良好的习惯，写出更健壮的代码，应参考LVTI的[Style Guidelines](https://openjdk.java.net/projects/amber/LVTIstyle.html)。如果不加后缀，数值推断为`int`，`float`可能会推断为`double`。因此，应该在字面量后面加上后缀。

**【正确示例】**

```
##### 场景1：使用不合适的后缀
- 修复示例1：

  ```java
  long sum = 0L;
  float flt = 1.0f; 
  double dbl = 2.0d; 
  ```


```
**【错误示例】**

```
##### 场景1：使用不合适的后缀
- 错误示例：

  ```java
  long sum = 0l; 
  float flt = 1;
  double dbl = 2.0;
  ```


```
**【修复建议】**

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
