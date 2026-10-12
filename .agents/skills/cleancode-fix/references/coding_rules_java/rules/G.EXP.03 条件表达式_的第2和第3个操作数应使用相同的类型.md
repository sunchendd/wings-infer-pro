# G.EXP.03 条件表达式?:的第2和第3个操作数应使用相同的类型

- **规则ID**：b951e856-c67a-4f95-8022-2a871534ec8b
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

条件运算符?:使用第1个操作数的布尔值决定后续表达式哪个被执行。但是Java语言有相当复杂的规则去判定表达式的结果类型，不一致的操作数类型，可能导致意料之外的类型转换。如第2和第3个操作数在类型对齐时，可能会因为自动拆箱导致NullPointerException。

**【正确示例】**

```
##### 场景1：表达式?:的第2和第3个操作数类型不一致
- 修复示例1：

  ```java
  char ch = 'A';
  int value = 50;
  boolean condition = ...; 
  System.out.println(condition ? ch : ((char) value));  // condition为true时，输出A ； 为false 时，输出 2
  Integer integer = null;
  System.out.print(condition ? integer : Integer.valueOf(value)); // condition为true时，输出 null
  ```


```
**【错误示例】**

```
##### 场景1：表达式?:的第2和第3个操作数类型不一致
- 错误示例：

  ```java
  char ch = 'A';
  int value = 50;
  boolean condition = ...; 
  System.out.println(condition ? ch : value); // condition为true时，输出65，自动将char类型转为int类型 ；为false 时，输出 50
  Integer integer = null;
  System.out.print(condition ? integer : value); // condition为true时，抛出NullPointerException
  ```


```
**【修复建议】**

三目运算符(`?:`)的第2和第3个操作数类型要保持一致。
