# G.CON.11 禁止使用Thread.stop()来终止线程 

- **规则ID**：6208ebac-5aae-487e-9ddf-fa465c43802f
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

Thread.stop() 已经被标记为@Deprecated，该方法是不安全的，调用 Thread.stop() 来终止线程 会使其释放它所持有的所有锁，可能会导致这些锁保护的对象处于不一致的状态

**【正确示例】**

```
使用一个标志来请求线程终止，设置线程结束标志。
public final class Foo implements Runnable {
    private volatile boolean shouldAbort = false;
    public void stop() {
        shouldAbort = true;
    }
    @Override
    public void run() {
        // ...
        while (!shouldAbort) {
            // ...
        }
    }
    public static void main(String[] args) {
        Foo foo = new Foo();
        Thread thread = new Thread(foo);
        thread.start();
        // ...
        foo.stop();
    }
}

```
**【错误示例】**

```
调用Thread的stop方法
public final class Foo implements Runnable {
    @Override
    public void run() {
        // ...
    }
    public static void main(String[] args) {
        Foo foo = new Foo();
        Thread thread = new Thread(foo);
        thread.start();
        // ...
        thread.stop();
    }
}

```
**【修复建议】**

禁止调用Thread.stop()
