# G.ERR.08 不要使用return、break、continue或抛出异常使finally块非正常结束

- **规则ID**：f9077ec4-e02c-4ae4-a9f1-75583a1cdfe2
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

在finally代码块中，直接使用return、break、continue、throw语句，或由于调用方法的异常未处理， 会导致finally代码块无法正常结束。非正常结束的finally代码块会影响try或catch代码块中异常的抛出， 也可能会影响方法的返回值。所以要保证finally代码块正常结束。

**【正确示例】**

```
main方法中捕获到异常。
public static void main(String[] args) {
    try {
        System.out.println(func());
    } catch (MyException ex) {
        // 处理异常
    }
}
public static int func() throws MyException {
    for (int i = 1; i < 2; i++) {
        try {
            throw new MyException();
        } finally {
            // ...
        }
    }
    return 0;
}

```
**【错误示例】**

```
main方法中不会捕获到异常，而是直接输出-1。
public static void main(String[] args) {
    try {
        System.out.println(func());
    } catch (MyException ex) {
        // 处理异常
    }
}
public static int func() throws MyException {
    for (int i = 1; i < 2; i++) {
        try {
            throw new MyException();
        } finally {
            return -1; // 不推荐
        }
    }
    return 0;
}

```
**【修复建议】**

将返回指令移到 finally 块之外。如果必须要 finally 块返回一个值，可以简单地将该返回值赋给一个本地变量，然后在 finally 块执行完毕后返回该变量
