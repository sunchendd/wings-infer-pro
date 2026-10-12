# G.CTL.02 含else if分支的条件判断应在最后加一个else分支

- **规则ID**：a1a3a3e8-874d-490f-9552-5f2720565caa
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

提示

**【描述】**

含多个else if条件组合的判断逻辑，往往会出现被遗漏的分支，在最后设置一个else分支可对遗漏场景进行处理（类似于switch-case语句要有default分支）。



最后的else分支如果没有明确的处理场景，可以记录一条日志或抛出异常等，如：`log("unknown condition")`、`throw new IllegalStateException("non-exhaustive cases")`等。

**【正确示例】**

```
##### 场景1：缺少else分支
- 修复示例1：

  ```java
  if ((employee.flags & HOURLEY_FLAG) && (employee.age > RETIRED_AGE)) {
      ...
  } else if ((employee.flags & HOURLEY_FLAG) && (employee.age < RETIRED_AGE)) {
      ...
  } else if ((employee.flags & HOURLEY_FLAG) && (employee.age == RETIRED_AGE)) {
      ...
  } else {
      ...
  }
  ```


```
**【错误示例】**

```
##### 场景1：缺少else分支
- 错误示例：

  ```java
  if ((employee.flags & HOURLEY_FLAG) && (employee.age > RETIRED_AGE)) {
      ...
  } else if ((employee.flags & HOURLEY_FLAG) && (employee.age < RETIRED_AGE)) {
      ...
  } else if ((employee.flags & HOURLEY_FLAG) && (employee.age == RETIRED_AGE)) {
      ...
  }
  ```


```
**【修复建议】**

在含多个else if条件组合的判断逻辑最后增加else分支。
