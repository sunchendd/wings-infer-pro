# SecJ_Lock_Synchronized

- **规则ID**：191eb18e-9dfa-4f75-801b-a63327e2befa
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

如果同步代码块（Synchronized）使用静态public的锁对象，或者锁对象被通过公有方法获得，攻击者可以获取该锁对象，最终引发DoS攻击。检查点：



1、检查同步块中的锁对象声明是否是public的，如果是则报告警。



2、检查同步块中的锁对象是否通过公有方法暴露给外部，如果是则报告警。

**【正确示例】**

```
场景一修复：同步块中的锁对象声明是private的。

```java

public class SomeObject {

// 【GOOD】同步块中的锁对象声明是private的。

private final Object lock = new Object();

public void changeValue() {

synchronized (lock) {

// ...

}

}

}

```

场景二修复：同步块中的锁对象没有通过公有方法暴露给外部。

```java

public class SomeObject {

private final Object lock = new Object();

public void changeValue() {

synchronized (lock) {

// ...

}

}

// 【GOOD】同步块中的私有锁对象没有通过公有方法暴露给外部。

}

```

```
**【错误示例】**

```
场景一：同步块中的锁对象声明是public的。

```java

public class SomeObject {

// 【不符合】同步块中的锁对象声明是public的。

public static final Object lock = new Object();

public void changeValue() {

synchronized (lock) {

// ...

}

}

}

// 不可信的代码调用

synchronized (SomeOjbect.lock) {

while (true) {

Thread.sleep(Integer.MAX_VALUE);

}

}

```

场景二、同步块中的私有锁对象通过公有方法暴露给外部。

```java

public class SomeObject {

private final Object lock = new Object();

public void changeValue() {

synchronized (lock) {

// ...

}

}

// 【不符合】同步块中的私有锁对象通过公有方法暴露给外部。

public Object getLock() {

return lock;

}

}

```

```
**【修复建议】**

1、同步块中的锁对象需使用私有锁。



2、同步块中的锁对象禁止通过公有方法暴露给外部。
