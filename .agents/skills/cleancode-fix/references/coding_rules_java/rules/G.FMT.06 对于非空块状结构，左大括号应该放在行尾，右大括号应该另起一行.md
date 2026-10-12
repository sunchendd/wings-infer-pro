# G.FMT.06 对于非空块状结构，左大括号应该放在行尾，右大括号应该另起一行

- **规则ID**：b6fc2716-5b97-42b0-92a1-eb7c5ffe7bfb
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

对于非空块状结构（含初始化块），大括号应该遵循K&R风格：



- 左大括号不换行；

- 右大括号自己单独一行；

- 右大括号后，可以跟逗号、分号等，也可以跟随 `else`、 `catch`、`finally`等关键字语句。

**【正确示例】**

```
##### 场景1
- 修复示例1：遵循K&R风格换行

  ```java
  try {
      if (condition()) {
          doSomething();
      } else {
          doSomethingElse();
      }
  } catch (MyException ex) {
      handleException(ex);
  }
  ```


```
**【错误示例】**

```
##### 场景1
- 错误示例：

  ```java
  try {
      doSomething();
  } catch (MyException ex) { handleException(ex); } // 【不符合】代码块应该换行
  ```


```
**【修复建议】**

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
