# G.CTL.04 循环必须保证可正确终止

- **规则ID**：a4fd6fbf-0645-44de-ba6d-fa7f4957640d
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

严重

**【描述】**

`while(true)`循环语句中如果缺少break，可能会导致循环无法终止。



另外，代码中更不应该出现空的无限循环，编写一个空的循环体，不会完成具体功能，反倒可能会消耗CPU；另一方面，如果刻意编写空循环来消耗CPU，却又可能被编译器或者JIT优化而消除。



例外场景：在线程的run方法里使用无限循环。

**【正确示例】**

```
##### 场景1：缺少break语句导致无限循环
- 修复示例1：

  ```java
  public void notAlwaysRun() {
      while (true) {
          if(condition()) {
              doSomething();
              break;
          } else{
              doSomethingElse();
          }
      }
  }
  ```
- 修复示例2：

  ```java
  public void notAlwaysRun() {
      int index = 0;
      while (index < 100) {
          if(condition(index)) {
              doSomething();            
          } 
          index ++;
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1：缺少break语句导致无限循环
- 错误示例：

  ```java
  public void alwaysRun() {
      while (true) {
          if(condition()) {
              doSomething();
          } else{
              doSomethingElse();
          }
      }
  }
  ```


```
**【修复建议】**

要为循环语句设置合理的终止条件，或添加合理终止循环的语句。
