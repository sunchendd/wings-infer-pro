# G.CLS.08-CPP delete操作符、移动构造函数、移动赋值操作符、swap函数应该有noexcept声明

- **规则ID**：2a6a6d61-f131-4a80-8511-27fb76cd27c5
- **更新时间**：2025-03-25 19:22:09

---

**【问题级别】**

一般

**【描述】**

这些操作会被某些C++表达式隐式调用，或被标准库调用，调用时不期望异常抛出。



和析构函数一样，operator delete函数会在堆中分配（new）的对象被析构的时候被调用，而析构函数很多情况下会在已经抛出异常的时候执行，以清理资源。但是，在已经有异常抛出的情况下抛异常，会导致std::terminate。



一些标准库的类或算法会依赖“移动构造函数、移动赋值操作符、swap函数不会抛异常”这些性质才能保证正常工作。例如：std::vector<T>::push_back(T&& value)可以保证“强异常安全”，即：如果执行过程中发生异常（如内存不足），这个函数没有任何副作用。但是，它的参数T&& value需要用移动构造函数移动到std::vector中。如果T的移动构造函数会抛异常，就不能保证强内存安全。

**【正确示例】**

```
##### 场景1：delete操作符没有noexcept声明
- 修复示例：

```cpp
class Message {
public:
    ...
    void operator delete(void *ptr) noexcept;   // 符合
    void operator delete[](void *ptr) noexcept; // 符合
};
```
##### 场景2：移动构造函数、移动赋值操作符没有noexcept声明
- 修复示例：

```cpp
class Message {
public:
    ...
    Message(Message&& other) noexcept;               // 不符合：无noexcept声明
    Message& operator=(Message&& other) noexcept;    // 不符合：无noexcept声明
};
```
##### 场景3：swap函数没有noexcept声明
- 修复示例：

```cpp
void swap(Message &x, Message &y) noexcept // 符合
{
    x.swap(y);
}
```
##### 场景4：给函数加"throw"异常说明
- 修复示例：

```cpp
void Call1() noexcept;  // 符合：noexcept表示函数不允许抛出任何异常
void Call2();           // 符合：无需专门标记抛出什么异常
void Call3();           // 符合：无需专门标记抛出什么异常
```

```
**【错误示例】**

```
auto?aa?=?ca;?????????// int,?忽略?const?和?reference

```
**【修复建议】**

添加noexcept声明
