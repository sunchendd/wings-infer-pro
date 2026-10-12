# G.RES.06-CPP 避免lambda表达式使用默认捕获模式

- **规则ID**：9dc982aa-783a-4e94-bc8c-a4e3d51a087c
- **更新时间**：2025-03-25 19:22:33

---

**【问题级别】**

一般

**【描述】**

lambda表达式提供了两种默认捕获模式：按引用（&）和按值（=）。



默认按引用捕获会隐式的捕获所有局部变量的引用，容易导致访问悬空引用。相比之下，显式的写出需要捕获的变量可以更容易的检查对象生命周期，减小犯错可能。



默认按值捕获会隐式的捕获this指针，且难以看出lambda函数所依赖的变量是哪些。如果存在静态变量，还会让阅读者误以为lambda复制了一份静态变量。



因此，通常应当明确写出lambda需要捕获的变量，而不是使用默认捕获模式。

**【正确示例】**

```
auto Fun()
{
    int addend = 0;
    static int baseValue = 0;

    return [addend, value = baseValue]() mutable { // 使用C++14的捕获初始化一个变量
        ++value;                                   // 不会影响Fun函数中的静态变量
        return value + addend;
    };
}
class SomeClass {
public:
    void Foo()
    {
        int value = 1;

        // 符合：显式指定按值捕获，减少混淆
        auto lambda = [value, this]() { std::cout << value << ", " << data; };

        value = 2;
        data = 3;
        lambda(); // 由于显式指定了value和this，此处明确输出1, 3
    }

private:
    int data = 0;
};

```
**【错误示例】**

```
auto Fun()
{
    int addend = 0;
    static int baseValue = 0;

    return [=]() {                                 // 实际上只复制了addend
        ++baseValue;                               // 修改会影响静态变量的值
        return baseValue + addend;
    };
}
class SomeClass {
public:
    void Foo()
    {
        int value = 1;

        // 不符合：看起来像是按值捕获，实际上是按引用捕获了成员变量
        auto lambda = [=]() { std::cout << value << ", " << data; };

        value = 2;
        data = 3;
        lambda(); // 可能会认为输出1, 0，实际输出1, 3
    }

private:
    int data = 0;
};

```
**【修复建议】**

显式指定按值或按引用捕获方式
