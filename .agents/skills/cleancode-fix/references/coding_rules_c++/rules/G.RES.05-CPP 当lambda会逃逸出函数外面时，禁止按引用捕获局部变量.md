# G.RES.05-CPP 当lambda会逃逸出函数外面时，禁止按引用捕获局部变量

- **规则ID**：5c36a116-d2e6-460f-b525-cd0c9e438cc0
- **更新时间**：2025-03-25 19:22:33

---

**【问题级别】**

严重

**【描述】**

如果一个 lambda 不止在局部范围内使用，禁止按引用捕获局部变量，比如它被传递到了函数的外部，或者被传递给了其他线程的时候。lambda按引用捕获就是把局部对象的引用存储起来。如果 lambda 的生命周期会超过局部变量生命周期，则可能导致内存不安全。

**【正确示例】**

```
void Foo()
{
    int local = 0;
    // 按值捕获 local, 在Process() 调用过程中，local 总是有效的
    threadPool.QueueWork([local] { Process(local); });
}

```
**【错误示例】**

```
void Foo()
{
    int local = 0;
    // 按引用捕获 local，当函数返回后，local 不再存在，因此 Process() 的行为未定义
    threadPool.QueueWork([&] { Process(local); });
}

```
**【修复建议】**

禁止按引用捕获局部变量
