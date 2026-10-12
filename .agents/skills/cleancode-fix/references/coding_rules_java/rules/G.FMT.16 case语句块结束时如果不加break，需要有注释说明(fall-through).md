# G.FMT.16 case语句块结束时如果不加break，需要有注释说明(fall-through)

- **规则ID**：27d92c0c-98cb-4edf-9823-5355c4052bd9
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

switch语句中，当没有终止语句（`break`，`return`或抛出异常）时会执行到switch语句的结束处。当case语句块中没有终止语句时，需要添加注释，表明会继续执行到下一个case语句块。任何符合fall-through概念的注释都可以（通常是`// $FALL-THROUGH$`）。



Eclipse和IntelliJ IDEA支持`$FALL-THROUGH$`这种特殊的注释来suppress缺少`break`的告警。尽管这不是Java的标准，但它被主流的IDE支持，推荐优先使用。



**注意**：



- 当javac开启 `-Xlint:fallthrough`选项编译时 ，加与不加`$FALL-THROUGH$`，可能都会告警；修复此告警可以考虑改用`if else if`写法替代`switch case`。

- continue不能单独用于switch中，可用于循环中的switch中，continue的作用是跳出本次循环，所以case语句中使用continue时，还会影响循环代码块中后续代码的执行。



如果`case`语句是空语句，则可以不用加注释特别说明。

**【正确示例】**

```
##### 场景1： case语句块结束时无break
- 修复示例1：增加break

  ```java
  switch (label) {
      case 0:
      case 1:
          System.out.println("1");
          break;
      case 2:
          System.out.println("2");
          break;
      case 3:
          System.out.println("3");
          break;
      default:
          System.out.println("Default case!");
  ```
- 修复示例2：增加`$FALL-THROUGH$`注释

  ```java
  switch (label) {
      case 0:
      case 1:
          System.out.println("1");
          // $FALL-THROUGH$
      case 2:
          System.out.println("2");
          break;
      case 3:
          System.out.println("3");
          break;
      default:
          System.out.println("Default case!");
  ```


```
**【错误示例】**

```
##### 场景1： case语句块结束时无break
- 错误示例：

  ```java
  switch (label) {
      case 0:
      case 1:
          System.out.println("1");
      case 2:
          System.out.println("2");
      case 3:
          System.out.println("3");
          break;
      default:
          System.out.println("Default case!");
  }
  ```


```
**【修复建议】**

建议为每个case语句添加break，如果确实不需要添加break时，需要添加`$FALL-THROUGH$`注释。

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
