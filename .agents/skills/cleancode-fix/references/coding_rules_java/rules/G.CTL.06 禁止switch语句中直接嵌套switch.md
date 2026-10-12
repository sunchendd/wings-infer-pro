# G.CTL.06 禁止switch语句中直接嵌套switch

- **规则ID**：0371da1c-a61c-4265-9c3a-951318e7d99c
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

严重

**【描述】**

switch语句中直接嵌套switch语句，会增加代码的复杂度，代码的可读性也会变差。

**【正确示例】**

```
##### 场景1：switch语句嵌套
- 修复示例：

  ```java
  switch (condition1) {
      case "case1":
          doSomething(condition2);
          break;
      case "case2":
          doSomethingElse();
          break;
      default:
          doSomethingDefault();
  }
  ...
  private void doSomething(String condition2) {
      switch (condition2) {
          case "case1":
              doSomethingCase1();
              break;
          case "case2":
              doSomethingCase2();
              break;
          default:
              doSomethingDefault();
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1：switch语句嵌套
- 错误示例：

  ```java
  switch (condition1) {
      case "case11":
          switch (condition2) {
              case "case21":
                  doSomethingCase1();
                  break;
              case "case22":
                  doSomethingCase2();
                  break;
              default:
                  doSomethingDefault();
          }
          break;
      case "case12":
          doSomething();
          break;
      default:
          doSomethingDefault();
  }
  ```


```
**【修复建议】**

将嵌套的switch抽取成一个单独的方法。
