# G.CON.06 使用新并发工具代替wait()和notify()

- **规则ID**：f4eae617-e61d-4e4f-a553-56a9dd71cd7c
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

Java 5开始提供了更高级的并发工具，这些工具可以有效替代wait()和notify()。新开发的代码应该优先使用这些并发工具。



这些高级的并发工具主要位于java.util.concurrent中，包括：



Executor Framework：可参考G.CON.12 避免不加控制地创建新线程，应该使用线程池来管控资源;

并发集合（Concurrent Collection）：提供了高性能的并发实现的集合接口，在其内部实现了同步管理，不需要额外加锁，常用的并发集合包括ConcurrentHashMap、ConcurrentSkipListSet、ConcurrentLinkedQueue等；

同步器（Synchronizer）：为每种特定的同步需求提供了解决方案，常用的同步器包括Phaser、CountDownLatch、Semaphore等。

**【正确示例】**

```
##### 场景1：
- 修复示例： 

  ```java
    public class ProducerConsumerExample {
        private static final Lock lock = new ReentrantLock();
        private static final Condition product = lock.newCondition();
        private static final Condition consume = lock.newCondition();

        public static void main(String[] args) {
            LinkedList<Integer> buffer = new LinkedList<>();
            int maxSize = 10;
            Thread producer = new Thread(new Producer(buffer, maxSize));
            Thread consumer = new Thread(new Consumer(buffer));
            producer.start();
            consumer.start();
        }

        static class Producer implements Runnable {
            private LinkedList<Integer> buffer;
            private int maxSize;

            public Producer(LinkedList<Integer> buffer, int maxSize) {
                this.buffer = buffer;
                this.maxSize = maxSize;
            }


            public void run() {
                int num = 0;
                while (true) {
                    try {
                        lock.lock();
                        while (buffer.size() == maxSize) {
                            try {
                                product.await();
                            } catch (InterruptedException e) {
                                e.printStackTrace();
                            }
                        }
                        buffer.add(num++);
                        System.out.println("Produced: " + num);
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException e) {
                            e.printStackTrace();
                        }
                        consume.signal();
                    } finally {
                        lock.unlock();
                    }
                }
            }
        }

        static class Consumer implements Runnable {
            private final LinkedList<Integer> buffer;

            public Consumer(LinkedList<Integer> buffer) {
                this.buffer = buffer;
            }

            public void run() {
                while (true) {
                    try {
                        lock.lock();
                        while (buffer.isEmpty()) {
                            try {
                                consume.await();
                            } catch (InterruptedException e) {
                                e.printStackTrace();
                            }
                        }
                        int num = buffer.removeFirst();
                        System.out.println("Consumed: " + num);
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException e) {
                            e.printStackTrace();
                        }
                        product.signal();
                    } finally {
                        lock.unlock();
                    }
                }
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
    public class ProducerConsumerExample {
        public static void main(String[] args) {
            LinkedList<Integer> buffer = new LinkedList<>();
            int maxSize = 10;
            Thread producer = new Thread(new Producer(buffer, maxSize));
            Thread consumer = new Thread(new Consumer(buffer));
            producer.start();
            consumer.start();
        }

        static class Consumer implements Runnable {
            private final LinkedList<Integer> buffer;

            public Consumer(LinkedList<Integer> buffer) {
                this.buffer = buffer;
            }

            public void run() {
                while (true) {
                    synchronized (buffer) {
                        while (buffer.isEmpty()) {
                            try {
                                buffer.wait();
                            } catch (InterruptedException e) {
                                e.printStackTrace();
                            }
                        }
                        int num = buffer.removeFirst();
                        System.out.println("Consumed: " + num);
                        buffer.notifyAll();
                    }
                }
            }
        }

        static class Producer implements Runnable {
            private LinkedList<Integer> buffer;
            private int maxSize;

            public Producer(LinkedList<Integer> buffer, int maxSize) {
                this.buffer = buffer;
                this.maxSize = maxSize;
            }

            public void run() {
                int num = 0;
                while (true) {
                    synchronized (buffer) {
                        while (buffer.size() == maxSize) {
                            try {
                                buffer.wait();
                            } catch (InterruptedException e) {

                            }
                        }
                        buffer.add(num++);
                        System.out.println("Produced: " + num);
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException e) {
                            e.printStackTrace();
                        }
                        buffer.notifyAll();
                    }
                }
            }
        }
    }
  ```


```
**【修复建议】**

新开发的代码应避免使用wait()和notify()方法。
