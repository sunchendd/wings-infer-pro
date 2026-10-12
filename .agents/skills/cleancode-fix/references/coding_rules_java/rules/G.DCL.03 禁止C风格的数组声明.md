# G.DCL.03 禁止C风格的数组声明

- **规则ID**：da7f55c0-e55e-4da7-81f2-1ab69b2c6313
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

一般

**【描述】**

数组类型由数据元素类型紧跟中括号（[]）组成，数组声明格式应该是`String[] nonEmptyArray`，而不是`String nonEmptyArray[]`。



初始化数组时，数组中的最后一个元素后不要添加**逗号**，例如`String[] nonEmptyArray = {"these", "can", "change",};`。

**【正确示例】**

```
##### 场景1：数组声明格式错误
- 修复示例：

  ```java
  String[] nonEmptyArray = {"these", "can", "change"};
  ```
##### 场景2：数组初始化时，最后一个元素后有冗余的逗号
- 修复示例：

  ```java
  String[] nonEmptyArray = {"these", "can", "change"};
  ```


```
**【错误示例】**

```
##### 场景1：数组声明格式错误
- 错误示例：

  ```java
  String nonEmptyArray[] = {"these", "can", "change"};
  ```
##### 场景2：数组初始化时，最后一个元素后有冗余的逗号
- 错误示例：

  ```java
  String[] nonEmptyArray= {"these", "can", "change", };
  ```


```
**【修复建议】**

使用类似`String[] array`风格的数组声明方式；



数组初始化时，删除数组中最后一个元素后多余的逗号。

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
