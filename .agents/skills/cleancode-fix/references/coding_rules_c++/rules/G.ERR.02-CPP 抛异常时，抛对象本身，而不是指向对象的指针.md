# G.ERR.02-CPP 抛异常时，抛对象本身，而不是指向对象的指针

- **规则ID**：7aac9d1a-5d02-47f0-b589-405fa27f00ed
- **更新时间**：2025-03-25 19:22:39

---

**【问题级别】**

严重

**【描述】**

C++中推荐的抛异常方式是抛对象本身，而不是指向对象的指针。



用throw语句抛出异常的时候，会构造一个临时对象，称为“异常对象（exception object）”。这个异常对象的生命周期在C++语言中很明确：异常对象在throw时被构造；在某个捕获它的catch语句以throw以外的方式结束（即没有重新抛出）时，或者指向这个异常的std::exception_ptr对象被析构时析构。



抛出指针，会使回收被抛出对象的责任不明确。捕获异常的地方是否有义务对该指针进行delete操作，取决于该对象是如何分配的（例如静态变量，或者用new分配），以及这个对象是否被共享了。但是指针类型本身并不能表明这个对象的生命周期以及所有权，也就无法判断是否应该delete。如果应该delete却没有做，会造成内存泄露；如果不该delete却做了，会造成重复释放。

**【正确示例】**

```
try {
    if (SomeFunction()) {
        throw SomeException("reason 1");
    } else {
        throw SomeException("reason 2");
    }
} catch (const SomeException& e) {
    ...                                      // 符合：这里可以确定不需要delete
}

```
**【错误示例】**

```
static SomeException exc1("reason 1");

try {
    if (SomeFunction()) {
        throw &exc1;                         // 不符合：这是静态对象的指针，不应该delete
    } else {
        throw new SomeException("reason 2"); // 不符合：这是动态分配的，应该delete
    }
} catch (const SomeException* e) {
    delete e;                                // 不符合：这里不能确定是否需要delete
}

```
**【修复建议】**

抛出对象而非指针
