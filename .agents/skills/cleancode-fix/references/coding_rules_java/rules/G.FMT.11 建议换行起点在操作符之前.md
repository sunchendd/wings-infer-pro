# G.FMT.11 建议换行起点在操作符之前

- **规则ID**：0b5c3de9-9cd1-487e-96bb-0ba7e0c1aced
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

当语句过长，或者可读性不佳时，需要在合适的地方换行。换行时建议将操作符、连接符放在新的一行。

**【正确示例】**

```
##### 场景1：未合理换行
- 修复示例1：在合适处断行，尽量将操作符、连接符放在新的一行

  ```java
  Student student = Student.builder()
      .setName("zhangsan")
      .setAge(14)
      .setGrade("5年级")
      .setMajor("软件工程")
      .setNum("123456789")
      .build();
  ```


```
**【错误示例】**

```
##### 场景1：未合理换行
- 错误示例：

  ```java
  Student student = Student.builder().setName("zhangsan").setAge(14).setGrade("5年级").setMajor("软件工程").
      setNum("123456789").build();
  ```


```
**【修复建议】**

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
