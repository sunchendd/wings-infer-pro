# G.CON.02 在异常条件下，保证释放已持有的锁

- **规则ID**：d8ec151d-3db1-4982-b811-2825954a571b
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

锁对象如果不能正确释放，可能会导致阻塞或死锁问题。为了保证锁被正确释放，建议在finally中释放锁。



对于加锁操作应在try代码块外部实现，避免因为加锁操作出现异常导致加锁失败，进而导致在finally中释放锁时发生异常。

**【正确示例】**

```
##### 场景1：加锁期间抛出受检异常
- 修复示例：

```java
public final class Foo {
    private final Lock lock = new ReentrantLock();

    public void correctReleaseLock() {
        lock.lock();
        try {
            doSomething();
        } catch (MyBizException ex) {
            ... // 处理异常
        } finally {
            lock.unlock();
        }
    }

    private void doSomething() throws MyBizException {
        ...
    }
}
```
##### 场景2：加锁期间可能抛出运行时异常
- 修复示例：

```java
final class Foo {
    private final Lock lock = new ReentrantLock();

    public void correctReleaseLock(String value) {
        lock.lock();
        try {
            ...
            int index = Integer.parseInt(value);
            ...
        } finally {
            lock.unlock();
        }
    }
}
```

```
**【错误示例】**

```
##### 场景1：加锁期间抛出受检异常
- 错误示例：

```java
public final class Foo {
    private final Lock lock = new ReentrantLock();

    public void incorrectReleaseLock() {
        try {
            lock.lock();
            doSomething();
        } catch (MyBizException ex) {
            ... // 处理异常
        }
    }

    private void doSomething() throws MyBizException {
        ...
    }
}
```
##### 场景2：加锁期间可能抛出运行时异常
- 错误示例：

```java
final class Foo {
    private final Lock lock = new ReentrantLock();

    public void incorrectReleaseLock(String value) {
        lock.lock();
        ...
        int index = Integer.parseInt(value);
        ...
    }
}
```

```
**【修复建议】**

释放锁操作在finally代码块中实现。
