# G.CON.01 对共享变量做同步访问控制时需避开同步陷阱

- **规则ID**：dfcb37cc-ea25-47fc-b111-3e64c8e73f03
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

致命

**【描述】**

用作锁的对象声明时，必须添加final修饰符，防止进行多线程同步期间由于被指向其他对象导致无法正确实现同步。

**【正确示例】**

```
##### 场景1：锁对象使用final修饰
- 修复示例1：锁对象使用final修饰。
```java
public class SomeSharedResource {
    private final Object lock = new Object();

    public void updateResource() {
        synchronized (lock) {
            // 更新共享的资源
            ...
        }
    }
}
```

```
**【错误示例】**

```
##### 场景1：锁对象使用final修饰
- 错误示例：锁对象不使用final修饰

```java
public class SomeSharedResource {
    // 【不符合】  非final修饰
    private Object lock = new Object();

    public void updateResource() {
        synchronized (lock) {
            // 更新共享的资源
            ...
        }
    }
}
```

```
**【修复建议】**

锁对象必须使用final修饰。
