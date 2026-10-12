# G.CON.10 线程中断由业务代码来协作完成，慎用Thread.interrupt方法

- **规则ID**：6b6afaf4-b174-4752-bc25-df7a5f2c8c64
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

线程中断由业务代码来协作完成，**慎用Thread.interrupt方法，它依赖执行线程对interrupted status的处理逻辑**。在使用Thread.interrupt()方法请求目标线程中止时，仅仅是在目标线程上将interrupted status标记为true，目标线程本身需用Thread.interrupted()方法检查该标记，当状态为true时，应主动执行清理，并抛出InterruptedException。



在编写需要中止的多线程程序时，必须选用能够响应interrupt的标准库或第三方库。Java标准库中的会阻塞的方法（如Thread.sleep()或者SocketChannel.write()）一般会在interrupt之后抛出InterruptedException。但有些方法则不理会interrupt，如Socket.write()，必须回避这些方法。

**【正确示例】**

```
##### 场景1：
- 修复示例： 

```java
public static void main(String[] args) {    
    Thread thread = new MyThread();
    thread.start();
    ...
    thread.requestStop(); // 【GOOD】使用通知变量机制来控制线程的终止
}

class MyThread extends Thread {
    private volatile boolean hasStopRequested;

    public void requestStop() {
        hasStopRequested = true;
    }
	
    @Override
    public void run() {
        while (!hasStopRequested) {
            doSomething();
        }
    }
}
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：

```java
public static void main(String[] args) {    
    Thread thread = new MyThread();
    thread.start();
    ...
    thread.interrupt(); // 【不符合】预期使用interrupt机制终止线程，但线程无法被正确终止
}

class MyThread extends Thread {
    ...
    public void run() {
        boolean running = true;
        while (running) {
            try {
                doSomething();
            } catch (InterruptedException ex) {
                running = false;
            }
        }
    }
}
```


```
**【修复建议】**

1、优先使用协作式的线程同步机制来通知一个线程中止作业，如java.util.concurrent包中的各种synchronizer，加锁的共享变量、volatile共享变量等。



2、如果需要一个线程让另一个线程中止执行，Java API推荐的方式是，让被中止的线程在运行中周期性地查询自己是否被中止。如果发现自己被中止，则应该主动清理状态并中止执行，而不是忽略请求继续执行。
