# G.CON.01-CPP 使用条件变量的wait方法时，必须外加条件判断，并在循环中等待

- **规则ID**：6361531e-8df6-4821-9e41-d39a4788804f
- **更新时间**：2025-03-25 19:23:23

---

**【问题级别】**

一般

**【描述】**

单独使用条件变量（std::condition_variable）无法达到“等待某一条件达成”的目的。

主要有两个原因：



wait和notify发生的顺序不确定。如果一个线程在wait之前，另一个线程就已经使某个条件达成，并调用了notify方法，那么wait的线程就会一直等待下去，因为不会再有线程去调用notify方法了



虚假唤醒（spurious wakeup）。所谓虚假唤醒，指的是在等待条件变量的线程，即使在没有任何线程调用notify方法的时候，也可能被随机地唤醒。虚假唤醒产生的原因和系统的实现有关，但C++标准库、POSIX以及很多并发接口中的条件变量机制都允许虚假唤醒出现。为了应对虚假唤醒现象，使用条件变量时必须在循环中调用wait方法



推荐使用void wait(std::unique_lock<std::mutex>& lock, Predicate pred)方法。这个方法要求调用者提供自己的条件pred，而且内部会在循环中等待。

**【正确示例】**

```
如下代码中，在while循环中等待dataReady条件变为真。可以抵御虚假唤醒以及wait和notify的顺序的影响。
int data = 0;
std::mutex dataMutex;
bool dataReady = false;
std::condition_variable dataReadyCond;
void Thread1()
{
    std::unique_lock<std::mutex> lock(dataMutex);
    while (!dataReady) {
        dataReadyCond.wait(lock);                 // 在循环中发生虚假唤醒时会再次wait
    }
    Use(data);                                    // 执行到这里，data必然已经就绪
}
void Thread2()
{
    {
        std::lock_guard<std::mutex> lock(dataMutex);
        data = MakeData();
        dataReady = true;
    }
    dataReadyCond.notify_all();
}

```
**【错误示例】**

```
如下代码中，没有外加条件。如果Thread2在Thread1开始之前就执行完毕，那么Thread1就会永远在wait()方法上等待下去，尽管data在Thread1执行之前就已经就绪了。

int data;
std::mutex dataMutex;
std::condition_variable dataReadyCond;
void Thread1()
{
    std::unique_lock<std::mutex> lock(dataMutex);
    // 如果Thread2此时已经执行完了notify_all，下面的wait就会永远等下去
    dataReadyCond.wait(lock);
    Use(data);
}
void Thread2()
{
    {
        std::lock_guard<std::mutex> lock(dataMutex);
        data = MakeData();
    }
    dataReadyCond.notify_all();
}
如下代码中，增加了一个布尔变量dataReady作为条件，Thread1以dataReady为数据是否已经就绪的标准，如果Thread2先执行完，dataReady就是true，Thread1就不会执行wait。但如果wait时发生了虚假唤醒，就会在没有就绪的情况下去使用未被初始化的data。

int data;
std::mutex dataMutex;
bool dataReady = false;
std::condition_variable dataReadyCond;
void Thread1()
{
    std::unique_lock<std::mutex> lock(dataMutex);
    if (!dataReady) {
        dataReadyCond.wait(lock); // 可能发生虚假唤醒
    }
    Use(data);                    // 因虚假唤醒而执行到这里时，data并未就绪
}
void Thread2()
{
    {
        std::lock_guard<std::mutex> lock(dataMutex);
        data = MakeData();
        dataReady = true;
    }
    dataReadyCond.notify_all();
}

```
**【修复建议】**

1. 在循环中使用wait方法，并加上条件判断。

2. 推荐使用void wait(std::unique_lockstd::mutex& lock, Predicate pred) 方法。这个方法

要求调用者提供自己的条件pred ，而且内部会在循环中等待。
