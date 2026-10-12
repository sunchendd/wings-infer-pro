# G.TYP.11 基本类型优于包装类型，注意合理使用包装类型

- **规则ID**：1cbfebcd-3ccb-4e37-b3f7-072dbae280f0
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

Java有两种类型，基本类型（Primitive type）和引用类型（Reference type）。基本类型如`boolean`、`int`、`double`，引用类型如`String`、`List`。每一种基本类型都有其对应的包装类型（Wrapper classes），如对应`int`的是`Integer`。

检查如下场景：

1，for循环变量使用封装类

2，封装类直接使用`==`比较

**【正确示例】**

```
##### 场景1：
- 修复示例：for循环变量应该使用基本类型

  ```java
  for(int i = 0; i < 10; i++) {
      i++;
  }
  ```
##### 场景2：
- 修复示例：封装类的比较应该使用equals()方法

  ```java
  Integer var1=1;
  Integer var2=2;
  if (var.equals(var2)) {
    ...
  }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：for循环变量使用封装类

  ```java
  for(Integer i = 0; i < 10; i++) {
      i++;
  }
  ```
##### 场景2：
- 错误示例：封装类直接使用`==`比较

  ```java
  Integer var1=1;
  Integer var2=2;
  if (var == var2) {
    ...
  }
  ```


```
**【修复建议】**

尽量直接使用基本类型

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
