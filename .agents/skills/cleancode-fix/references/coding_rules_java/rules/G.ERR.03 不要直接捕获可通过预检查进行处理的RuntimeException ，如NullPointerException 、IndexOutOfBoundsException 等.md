# G.ERR.03 不要直接捕获可通过预检查进行处理的RuntimeException ，如NullPointerException 、IndexOutOfBoundsException 等

- **规则ID**：f7ce341d-bed2-4900-8313-67614379a5e4
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

一般

**【描述】**

可通过预检查的方式进行消除的RuntimeException，这类异常一般表示程序逻辑错误，不应该通过try...catch的方式进行处理（这也可能会影响代码的可读性及系统的运行效率）。推荐通过预检查方式进行消除，该类运行期异常包括：NullPointerException、IndexOutOfBoundsException等。对于NumberFormatException、IllegalArgumentException、IllegalStateException等可通过try...catch方式处理。

**【正确示例】**

```
##### 场景1：
- 修复示例1：

```java
public class SomeDemo {
    private boolean doSomething(String str) {
        if (str == null) {
            return false;
        }
        String[] names = str.split(" ");
        if (names.length != 2) {
            return false;
        }
        return (isCapitalized(names[0]) && isCapitalized(names[1]));
    }

    private boolean isCapitalized(String str) {
        for (int i = 0; i < str.length(); i++) {
            if (!(str.charAt(i) >= 'A' && str.charAt(i) <= 'Z')) {
                return false;
            }
        }
        return true;
    }
}
```

```
**【错误示例】**

```
##### 场景1：
- 错误示例：
```java
public class SomeDemo {
    private boolean doSomething1(String str) {
        try {
            String[] names = str.split(" ");

            if (names.length != 2) {
                return false;
            }
            return (isCapitalized(names[0]) && isCapitalized(names[1]));
            /* 不符合: Do not catch NullPointerException or any of its ancestors because it cannot help locate where the exception is thrown. */
        } catch (NullPointerException e) {
            return false;
        }
    }

    private boolean doSomething2(String str) {
        if (str == null) {
            return false;
        }
        try {
            String[] names = str.split(" ");
            return (isCapitalized(names[0]) && isCapitalized(names[1]));
            /* 不符合: Do not catch NullPointerException or any of its ancestors because it cannot help locate where the exception is thrown. */
        } catch (ArrayIndexOutOfBoundsException e) {
            return false;
        }
    }

    private boolean doSomething3(String str) {
        try {
            String[] names = str.split(" ");
            return (isCapitalized(names[0]) && isCapitalized(names[1]));
            /* 不符合: Do not catch NullPointerException or any of its ancestors because it cannot help locate where the exception is thrown. */
        } catch (ArrayIndexOutOfBoundsException | NullPointerException e) {
            return false;
        }
    }

    private boolean isCapitalized(String str) {
        for (int i = 0; i < str.length(); i++) {
            if (!(str.charAt(i) >= 'A' && str.charAt(i) <= 'Z')) {
                return false;
            }
        }
        return true;
    }
}
```

```
**【修复建议】**

通过**预检查的方式**消除NullPointerException、IndexOutOfBoundsException等异常。
