# G.CON.04 避免使用不正确形式的双重检查锁

- **规则ID**：efe4c95a-8496-4225-9956-4893c9873468
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

一般

**【描述】**

在使用使用双重检查锁时，不正确的使用双重检查锁，可能会导致线程发布一个未初始化或部分初始化的对象给另外的线程使用，存在延迟初始化的Java优化问题隐患。因此在产品使用时需要避免使用不正确形式的双重检查锁。

**【正确示例】**

```
##### 场景1：双重检测同步延迟加载。
- 修复示例：

```java
final class Singleton {
    // 使用 volatile 修饰，保证不同线程对这个变量进行操作时的可见性，并禁止进行指令重排序。
    private static volatile Singleton instance = null;
    private static final Object LOCK = new Object();

    private Singleton() {
        ...
    }

    public static Singleton getSingletonInstance() {
        if (instance == null) {
            synchronized (LOCK) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}
```


```
**【错误示例】**

```
##### 场景1：双重检测同步延迟加载。
- 错误示例：

```java
final class Singleton {
    private static Singleton instance = null;
    private static final Object LOCK = new Object();

    private Singleton() {
        ...
    }

    public static Singleton getSingletonInstance() {
        if (instance == null) {
            synchronized (LOCK) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}
```


```
**【修复建议】**

将双重检查锁涉及的单例类对象设置为volatile 。
