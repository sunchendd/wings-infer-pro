# G.CON.13 线程池中的任务结束后必须清理其自定义的ThreadLocal变量

- **规则ID**：e8672aac-6a6a-4057-8fea-f1e664913eb3
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

一般

**【描述】**

`ThreadLocal`基于弱引用实现，如果线程栈随着线程一起被JVM回收，`ThreadLocal`中存放的值也会在之后的GC被回收。而线程池技术则会重复使用线程以减少线程创建开销。这种线程的复用，导致`ThreadLocal`变量的使用存在以下两类问题：



- 脏数据问题：当前任务未正确初始化`ThreadLocal`变量，导致`ThreadLocal`变量取到该线程之前执行的某一个任务中设置的未清除的值；

- 内存泄露问题：任务中没有主动清理`ThreadLocal`中存放的值，且该线程池中的核心线程持有了`ThreadLocal`的引用，使得`ThreadLocal`中的值对象不会被JVM主动释放，最终造成这部分内存无法被回收导致内存泄露。



因此必须保证线程池中每个任务使用的`ThreadLocal`变量在任务结束后被主动清理。



一些常见的涉及线程池的场景包括但不限于：

1. 使用JDK或第三方线程池工具类提交异步任务：`ThreadPoolExecutor`、`ForkJoinPool`、来自`Guava`的增强线程池（通常继承自`ListeningExecutorService`）、来自`Spring`的异步线程池`org.springframework.core.task.TaskExecutor`等；

2. 基于线程池进行任务执行的框架或工具：JDK中的`java.util.Collection#parallelStream`（该接口默认复用`ForkJoinPool.commonPool()`）、Netty的`io.netty.channel.ChannelPipeline`中的`addAfter`和`addFirst`（使用线程池提交handler）、以及Tomcat/Jetty中的请求处理线程池等；

**【正确示例】**

```
##### 场景1：
- 修复示例：线程池中线程在finaly代码块中对ThreadLoacl变量进行清理
```java
class TestThreadLocalTask implements Runnable {
    private static ThreadLocal<Integer> localValue = new ThreadLocal<>();

    @Override
    public void run() {
        localValue.set(STATE1);
        try {
            ...
            localValue.set(STATE3);
	    doSomething(localValue.get());
            ...
        } finally {
            localValue.remove(); // 【GOOD】需要执行remove方法清理线程局部变量
        }
    }
}
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：线程池中线程对于ThreadLoacl变量使用结束后未清理

```java
public class TestThreadLocal {
    public static void main(String[] args) {
        ThreadPoolExecutor pool = new ThreadPoolExecutor(1, 2, 100,
            TimeUnit.MILLISECONDS, new LinkedBlockingQueue<Runnable>(),
            Executors.defaultThreadFactory(), new ThreadPoolExecutor.CallerRunsPolicy());
        for (int i = 0; i < 20; i++) {
            pool.execute(new TestThreadLocalTask());
        }
    }
}

class TestThreadLocalTask implements Runnable {
    private static ThreadLocal<Integer> localValue = new ThreadLocal<>();

    @Override
    public void run() {
        localValue.set(STATE1);
        try {
            ...
            doSomething(localValue.get());
            ...
        } catch(MyBizException ex){ 
	    ...	
        }
        // 【不符合】 ThreadLocal变量未清理
    }
}
```


```
**【修复建议】**

必须保证线程池中每个任务使用的`ThreadLocal`变量在任务结束后被主动清理（可以利用`finally`来实现）。
