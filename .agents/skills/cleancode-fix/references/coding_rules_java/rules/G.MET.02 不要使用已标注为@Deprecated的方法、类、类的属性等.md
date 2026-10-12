# G.MET.02 不要使用已标注为@Deprecated的方法、类、类的属性等

- **规则ID**：bbcc9ad7-f515-48d0-89b7-f95e9de6996d
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

标注为@Deprecated的方法、类、类的属性等，是由于各种原因被废弃的，为了保持兼容性而没有删除。新写的代码应避免继续使用这些方法、类等，而应该使用推荐的代替实现。

**【正确示例】**

```
##### 场景1：不要使用已标注为@Deprecated的方法、类、类的属性等
- 修复示例：使用非Deprecated的方法、类、类属性。

```java
    private static String message() {
        return "";
    }

    private String message2() {
        return "";
    }

    private void doSomething1() {
        String message = testClass.message();
        if (StringUtils.isEmpty(message)) {
            return;
        }
    }

    private void doSomething2() {
        String message = message2();
        if (StringUtils.isEmpty(message)) {
            return;
        }
    }
```


```
**【错误示例】**

```
##### 场景1：不要使用已标注为@Deprecated的方法、类、类的属性等
- 错误示例：

```java
    @Deprecated
    private static final String deprecated = "";

    @Deprecated
    private static String message() {
        return "";
    }

    @Deprecated
    private String message2() {
        return "";
    }

    private void doSomething1() {
        // 【不符合】 Do not use deprecated class, method or field.
        String message = message();
        if (StringUtils.isEmpty(message)) {
            return;
        }
    }

    private void doSomething2() {
        // 【不符合】 Do not use deprecated class, method or field.
        String message = DeprecatedClass.message();
        if (StringUtils.isEmpty(message)) {
            return;
        }
    }

    private void doSomething3() {
        // 【不符合】 Do not use deprecated class, method or field.
        DeprecatedClass deprecatedClass = new DeprecatedClass();

        // 【不符合】 Do not use deprecated class, method or field.
        if (StringUtils.isEmpty(deprecatedClass.a)) {
            return;
        }
    }
```


```
**【修复建议】**

不要使用已标注为@Deprecated的方法、类、类的属性等
