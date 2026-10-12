# G.CON.08 使用Thread对象的setUncaughtExceptionHandler方法注册未捕获异常处理者

- **规则ID**：4c90ee22-3998-4ee5-ab43-0248f6b64805
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

严重

**【描述】**

Java多线程程序中，所有线程都不允许抛出未捕获的checked exception，也就是说各个线程需要自己把自己的checked exception处理掉。但是无法避免未捕获的RuntimeException。当子线程抛出异常时，子线程会结束，但主线程不会知道，因为主线程通过try-catch是无法捕获子线程异常的。



Thread对象提供了setUncaughtExceptionHandler方法用来获取线程中产生的异常。还可以使用Thread.setDefaultUncaughtExceptionHandler，为所有线程设置默认异常处理方法。



应注意的是，在执行周期性任务例如ScheduledExecutorService时，为了程序的健壮性，可考虑在提交的Runnable的run方法内捕获高层级的异常。



ScheduledExecutorService的各种schedule方法，可以通过其返回的ScheduledFuture对象获取其异常。

**【正确示例】**

```
##### 场景1：
- 修复示例： 


  ```java
    public class TestUncaughtException {
        public static void main(String[] args) {
            TestThread thread = new TestThread("meaningful-name");
            thread.setUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {
                @Override
                public void uncaughtException(Thread tr, Throwable ex) {
                    System.out.println(tr.getName() + " : " + ex.getMessage());
                }
            });
            thread.start();
        }
        public static class TestThread extends Thread {
            public TestThread(String name) {
                super.setName(name);
            }

            @Override
            public void run() {
                ...
                throw new RuntimeException("just a test");
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
    public class TestUncaughtException {
        public static void main(String[] args) {
            TestThread thread = new TestThread("meaningful-name");
            thread.start();
        }
        public static class TestThread extends Thread {
            public TestThread(String name) {
                super.setName(name);
            }

            @Override
            public void run() {
                ...
                throw new RuntimeException("just a test");
            }
        }
    }
  ```


```
**【修复建议】**

创建线程时设置异常处理方法，保证线程抛出的异常可以被正确处理。
