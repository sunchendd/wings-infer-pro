# G.MET.03 不应把方法的参数当做临时变量

- **规则ID**：8e6405ac-d48a-4c39-a8e7-71d60160beb1
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

提示

**【描述】**

不应把方法的参数当做临时变量，因为每个变量/参数都有自己独特的功用，让一个变量承担多个职责，变量名将无法清晰表达其功能，会使程序难以理解。

**【正确示例】**

```
##### 场景1：
- 修复示例：在方法中定义临时变量替代方法参数

```java
// 【GOOD】使用final能够帮助判断，避免意外修改。
int doSomething(final int basicSalary) {
    int performanced = basicSalary * getMultiplier(basicSalary);
    int bonused = performanced + getAdder(performanced);
    ...
    return bonused;
}
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：方法参数用作临时变量，在方法中对其进行了修改

```java
// 【不符合】方法参数用作临时变量。
int doSomething(int inputData) {
    inputData = inputData * getMultiplier(inputData);
    inputData = inputData + getAdder(inputData);
    return inputData;
}
```


```
**【修复建议】**

在方法体中，应该避免对方法参数进行修改，包括重新赋值、自增/自减运算。如果需要，可以定义一个新的临时变量替代方法参数。
