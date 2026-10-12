# SecJ_Return_Inside_Finally

- **规则ID**：d349bb9c-d819-4020-a676-635af4365bb2
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

在finally代码块中，直接使用return语句会导致finally代码块无法正常结束。非正常结束的finally代码块会影响try或catch代码块中异常的抛出，也可能会影响方法的返回值。所以要保证finally代码块正常结束。

**【正确示例】**

```
```java

public static void test01Bad() {

try {

return;

} finally {

/* 【GOOD】: 在finally不使用返回语句 */

closeResource();

}

}



```

```
**【错误示例】**

```
```java

public static void test01Bad() {

try {

throw new RuntimeException("Run Exception");

} finally {

/* 【不符合】: 在finally直接使用了return语句. */

return;

}

}

```

```
**【修复建议】**

将返回指令移到 finally 块之外。如果必须要 finally 块返回一个值，可以简单地将该返回值赋给一个本地变量，然后在 finally 块执行完毕后返回该变量。
