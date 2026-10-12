# SecJ_Dead_Code_Always_True_Or_False

- **规则ID**：c286d7be-01e6-459a-a8ed-0e154b75ff0b
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

无效或永不执行的代码（即无效代码或无法访问的代码）通常是编程错误的结果，并且可能导致意外行为。通常在编译时，编译器会对此类代码进行优化。但是，为了提高可读性并确保解决逻辑错误，应该将这类代码直接删除。

**【正确示例】**

```
```java

boolean canEvaluate = false;

if(condition()) {

canEvaluate = true; // 【GOOD】修改变量`canEvaluate`的值为`true`，让`doSomething()`可以执行到。

}

...

if(canEvaluate) {

doSomething();

}

```

```
**【错误示例】**

```
```java

boolean canEvaluate = false;

if(condition()) {

canEvaluate = false;

}

...



// 【不符合】由于变量`canEvaluate`的值始终为`false`，导致`doSomething()`始终无法执行。

if(canEvaluate) {

doSomething();

}

```

```
**【修复建议】**

删除无效或从未执行代码；或者修改逻辑，以保障代码能够执行到。
