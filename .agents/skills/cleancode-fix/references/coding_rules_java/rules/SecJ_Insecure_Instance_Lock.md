# SecJ_Insecure_Instance_Lock

- **规则ID**：aaa7cd5b-e4f6-481c-8d94-b0816b7114ff
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

实例锁的同步效果仅限于此实例本身，无法用来同步静态共享变量；如果试图使用实例锁来同步静态共享变量，在多实例情况下无法实现符合预期的同步效果

**【正确示例】**

```
```java

public class CWE667_J_Rule5_5_Insecure_Instance_Lock_01_Good implements Runnable {

private static int counter;

private static final Object LOCK = new Object();



@Override

public void run() {

/* 【GOOD】: 程序使用类锁来保护静态共享数据 */

synchronized (LOCK) {

counter++;

// ...

}

}

}

```

```
**【错误示例】**

```
```java

public class CWE667_J_Rule5_5_Insecure_Instance_Lock_01_Bad implements Runnable {

private static int counter;

private final Object lock = new Object();



@Override

public void run() {

/* 【不符合】: 程序不能使用实例锁来保护静态共享数据，因为实例锁在两个或多个实例的情况下是无效的，导致并发时的线程同步失效 */

synchronized (lock) {

counter++;

// ...

}

}

}



```

```
**【修复建议】**

实例锁无法保护静态数据，应该使用类锁保护静态共享数据



[具体解释](https://blog.csdn.net/cs408/article/details/48930803)
