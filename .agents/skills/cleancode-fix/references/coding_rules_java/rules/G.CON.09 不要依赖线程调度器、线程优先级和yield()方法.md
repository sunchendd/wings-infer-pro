# G.CON.09 不要依赖线程调度器、线程优先级和yield()方法

- **规则ID**：43abec2b-a344-4c85-b555-3122504f0575
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

Java中的线程调度，是基于操作系统以及JVM的实现，在不同的操作系统中，或者不同厂商的JVM（如Oracle、IBM等），即使是同一套代码，其多线程的调度机制也是不一样的。因此，在多线程的程序中，不要依赖于系统的线程调度器来决定程序的逻辑运作，如果程序依赖于线程调度器来达到正确性或者性能要求，会导致不可移植。



线程的优先级是高度依赖于系统的。当虚拟机依赖于系统的线程实现机制时，Java线程的优先级会被映射到系统的线程优先级上，Java线程优先级的数量会发生变化，甚至可能被忽略。所以程序功能的正确性不能依赖于线程的优先级。



而Thread.yield()对线程调度器仅仅是个提示，不保证确定的效果，因此代码也不能依赖Thread.yield()方法。

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
                    while (buffer.isEmpty()) {
                        Thread.yield();
                    }
                    int num = buffer.removeFirst();
                    System.out.println("Consumed: " + num);
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
                    while (buffer.size() == maxSize) {
                        Thread.yield();
                    }
                    buffer.add(num++);
                    System.out.println("Produced: " + num);
                    try {
                        Thread.sleep(1000);
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
                }
            }
        }
    }
  ```


```
**【修复建议】**

线程的运行应避免依赖通过setPriority()、Thread.yield()等方法设置的线程优先级。
