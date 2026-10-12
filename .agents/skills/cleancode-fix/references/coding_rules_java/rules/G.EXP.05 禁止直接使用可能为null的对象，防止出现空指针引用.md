# G.EXP.05 禁止直接使用可能为null的对象，防止出现空指针引用

- **规则ID**：762d3b0b-e97b-4372-955d-f67abf1ce090
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

严重

**【描述】**

在Java中，禁止直接使用可能为null的对象是为了避免空指针异常（NullPointerException）。当程序试图访问一个空对象的属性、调用其方法或操作其字段时，就会抛出这种异常。这通常表示程序逻辑中存在错误，因为预期该对象应该是已初始化且非空的。



常见涉及空指针引用包括但不限于以下场景：

1、声明为null的变量在返回前存在else分支未对变量进行初始化或赋值。

2、声明为null的变量在try-catch中赋值，发生异常后，仅记录了日志而未进一步抛出异常，导致变量未正确赋值。

**【正确示例】**

```
##### 场景1：
- 修复示例：对于方法返回值可能为null时，方法返回值使用前进行判空处理
```java
public String getData() {
    return data == null ? null : data.toUpperCase();
}

public void doSomething() {
    ...
    String data = getData();
    /* GOOD : data在使用前先判空 */
    if (data != null && data.startsWith("XXX")) {
        ...
    }
    ...
}
```

```
**【错误示例】**

```
##### 场景1：
- 错误示例：对于方法返回值可能为null时，方法返回值使用前未做判空处理

```java
public String getData() {
    return data == null ? null : data.toUpperCase();
}

public void doSomething() {
    ...
    String data = getData();
    /* 不符合 : data可能会返回null，存在空指针风险 */
    if (data.startsWith("XXX")) {
        ...
    }
    ...
}
```

```
**【修复建议】**

通过预检查（即在操作对象之前检查其是否为null），我们可以提前发现并处理这种潜在的错误，而不是依赖于运行时的异常处理机制。预检查可以通过简单的条件语句实现，如** if (object != null) { ... } **。这样可以确保只有当对象确实存在时，才会执行后续的操作，从而避免了空指针异常，提高了代码的健壮性和可靠性。
