# G.CON.02-CPP 不要直接调用mutex的方法

- **规则ID**：3acf687f-78e3-457d-93e6-8526505fa548
- **更新时间**：2025-03-25 19:23:24

---

**【问题级别】**

一般

**【描述】**

std::mutex以及std::shared_mutex等锁对象提供lock()和unlock()方法来进行加锁和解锁。但是，直接调用这两个方法很容易造成执行不到unlock的错误。



应该使用std::lock_guard、std::unique_lock等机制，确保以任何形式（正常执行完、中途break、continue、返回、抛异常等）离开作用域时都会自动调用unlock()解锁。



注：std::unique_lock的不同构造函数可以用来调用try_lock、try_lock_for、try_lock_until等方法，而不仅仅是lock方法。

**【正确示例】**

```
使用std::lock_guard后，任何出口都会自动解锁。

Data* data = nullptr;
std::mutex dataMutex;

Data& GetData()
{
    std::lock_guard<std::mutex> lock(dataMutex);

    if (data != nullptr) {
        return *data;      // return时lock析构，自动unlock
    }
    data = CreateData();   // 如果这里抛异常（只要能被catch）也会使lock析构，自动unlock
    return *data;          // return时lock析构，自动unlock
}

```
**【错误示例】**

```
如下代码中，很容易看出在return之前忘记unlock了。当函数变大，出口变多，甚至有异常抛出时，这样的错误很难避免。

Data* data = nullptr;
std::mutex dataMutex;

Data& GetData()
{
    dataMutex.lock();
    if (data != nullptr) {
        return *data;      // 忘记unlock
    }
    data = CreateData();   // 如果这里抛异常，也无法unlock
    dataMutex.unlock();
    return *data;
}

```
**【修复建议】**

不要直接调用mutex的方法。std::mutex以及std::shared_mutex等锁对象提供lock()和unlock()方法来进行加锁和解锁。直接调用这两个方法很容易造成执行不到unlock的错误。 建议使用std::lock_guard、std::unique_lock等机制，确保以任何形式（正常执行完、中途break、continue、返回、抛异常等）离开作用域时都会自动调用unlock()解锁。
