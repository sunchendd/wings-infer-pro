# G.FMT.18 块注释的缩进级别应与上下文代码相同

- **规则ID**：90eda2fb-b127-46f1-9909-5b91291a11c3
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

块注释的缩进级别应该与被注释代码相同。可以采用单行注释（`// ...`）风格或多行注释（`/* ... */`）风格，对于多行注释风格，每行注释要以`*`开头且保持前后对齐

**【正确示例】**

```
##### 场景1：注释与代码不对齐
- 修复示例1：遵循K&R风格换行

  ```java
  public void doSomething() {
      ...
      if(condition()) {
          /*
           * 第一行注释
           * 第二行注释
           */
          int value = 0;
      }
      ...
  }
  public void doSomething() {
      ...
      if(condition()) {
          // 第一行注释
          // 第二行注释
          int value = 0;
      }
      ...
  }
  ```


```
**【错误示例】**

```
##### 场景1：注释与代码不对齐
- 错误示例：

  ```java
  public void doSomething() {
      ...
      if(condition()) {
           /*
            * 第一行注释
            * 第二行注释
            */
          int value = 0;
      }
      ...
  }
  public void doSomething() {
      ...
      if(condition()) {
            // 第一行注释
         // 第二行注释
          int value = 0;
      }
      ...
  }
  ```


```
**【修复建议】**

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
