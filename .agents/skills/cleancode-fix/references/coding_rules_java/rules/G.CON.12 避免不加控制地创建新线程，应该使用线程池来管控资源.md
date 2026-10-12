# G.CON.12 避免不加控制地创建新线程，应该使用线程池来管控资源

- **规则ID**：42d61992-2782-46ea-a9c1-7bb47c9bfeb3
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

Java虚拟机能够管理的线程数量有限，不加控制的创建新线程可能会导致Java虚拟机崩溃。



推荐使用Java 5之后提供的线程池ThreadPoolExecutor来管理线程资源，这样可以更加明确线程池的运行规则，避免资源耗尽的风险。另外，线程池要合理规划，避免任意重复创建。



不推荐使用Executors创建线程池，因为存在以下问题：



1）Executors.newFixedThreadPool()和Executors.newSingleThreadExecutor()允许请求队列的最大长度为Integer.MAX_VALUE，可能会因为堆积大量的请求导致OOM。



2）Executors.newCachedThreadPool()允许创建线程的最大数量为Integer.MAX_VALUE，可能会因为创建大量的线程导致OOM。Executors.newScheduledThreadPool()会自动增长工作队列大小。Executors.newWorkStealingPool()实际的工作窃取线程数量会动态地增减。

**【正确示例】**

```
##### 场景1：
- 修复示例： 使用线程池机制

  ```java
    private BlockingQueue blockingQueue = new LinkedBlockingQueue(100);
    private ThreadPoolExecutor threadPool = new ThreadPoolExecutor(2, 64, 60L,
        TimeUnit.SECONDS, blockingQueue,
        new SelfThreadFactory("ProductName", "ThreadName", false),
        new DiscardOldestPolicy(LOGGER, "ThreadName"));
    public void processEntity2(List<Entity> items) {
        for (Entity entity : items) {
            threadPool.execute(new EntityProcessor(entity));
        }
    }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例1：单独创建线程

  ```java
    public void processEntity(List<Entity> items) {        
        ...       
        new Thread(new EntityProcessor(entity)).start();
        ...       
    }
  ```
- 错误示例2：在循环中创建多个线程

  ```java
    public void processEntity(List<Entity> items) {
        for (Entity entity : items) {
            new Thread(new EntityProcessor(entity)).start();
        }
    }
  ```


```
**【修复建议】**

避免单独创建线程，尽量使用线程池来复用线程。线程池的从创建推荐使用ThreadPoolExecutor。
