# G.TYP.06 禁止尝试与NaN进行比较运算，相等操作使用Double或Float的isNaN()方法

- **规则ID**：6ae7aa49-b0aa-4c21-97fa-5b1d481bd272
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

严重

**【描述】**

当任意一个操作数是NaN（Not a Number）时，数值比较运算符<、<=、>、>=会返回false，运算符==会返回false，运算符!=会返回true。因为无序的特性常常会导致意外结果，所以不能直接与NaN进行比较。

**【正确示例】**

```
##### 场景1：数值直接与NaN比较
- 修复示例1：

  ```java
  public class NanComparison {
      public void doSomething(double num) {
          // 如果num的值为0.0d，则Math.cos(infinity)返回NaN
          double result = Math.cos(1 / num);
          if (Double.isNaN(result)) {
              System.out.println("result is NaN");
          }
          ...
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1：数值直接与NaN比较
- 错误示例：

  ```java
  public class NanComparison {
      public void doSomething(double num) {
          // 如果num的值为0.0d，则Math.cos(infinity)返回NaN
          double result = Math.cos(1 / num);
          if (result == Double.NaN) { // 相等比较总是false
              System.out.println("result is NaN");
          }
          ...
      }
  }
  ```


```
**【修复建议】**

用Double或Float的`isNaN()`方法判断浮点数是否为`NaN`。
