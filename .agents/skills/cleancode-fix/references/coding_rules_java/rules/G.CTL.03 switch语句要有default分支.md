# G.CTL.03 switch语句要有default分支

- **规则ID**：4a315130-05a5-4fcf-a06c-0911292476cd
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

每个switch语句都应该包含一个default分支，即使default分支没有业务逻辑代码。default分支中没有业务逻辑代码时，可以记录一条日志或抛出异常等，如：`log("unknown condition")`、`throw new IllegalStateException("non-exhaustive cases")`等。

**【正确示例】**

```
##### 场景1：缺乏default分支
- 修复示例1：

  ```java
  switch(d) {
  case 2:
      ...
      break;
  case 3:
      ...
      break;
  default:
      ...
      break;
  }
  ```


```
**【错误示例】**

```
##### 场景1：缺乏default分支
- 错误示例：

  ```java
  switch(d) {
  case 2:
      ...
      break;
  case 3:
      ...
      break;
  }
  ```


```
**【修复建议】**

switch语句中增加default分支。
