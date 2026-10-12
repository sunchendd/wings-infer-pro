# G.STD.18-CPP 使用库函数时避免竞争条件

- **规则ID**：d120102f-08fd-49c5-98b8-70c59ea22e82
- **更新时间**：2025-03-25 19:23:33

---

**【问题级别】**

一般

**【描述】**

在编写含有并发操作的程序时，使用库函数可能会产生竞争条件。例如：C语言标准库的strtok函数返回一个指向静态缓冲区的指针，在多线程中使用时存在竞争条件，可能造成非预期的结果，可以使用strtok_r函数避免该问题。



C++标准库中定义的大多数类型（如容器类型等）构造的对象，在多线程情况下共享使用（如调用对象方法改变对象状态），通常是非线程安全的。部分对象如std::cout，std::cin的线程安全可由标准保证；但多线程下同时操作一个对象会引起交错的输出，或者非预期的输入。



因此，使用库函数前需要仔细阅读函数说明文档，避免因并发操作而产生的竞争条件问题。

**【正确示例】**

```
如下代码中，先将取到的环境变量保存起来，然后再比较。

// 函数是将srcEnv复制一份。
static std::string TransEnv(const char* srcEnv)
{
    ...
}

void Fun()
{
    const char* envVal = getenv("TABLE_WX_ENV");
    if (envVal == nullptr) {
        ... // 错误处理
        return;
    }
    std::string wxEnv = TransEnv(envVal);

    envVal = getenv("TABLE_BD_ENV");
    if (envVal == nullptr) {
        ... // 错误处理
        return;
    }
    std::string bdEnv = TransEnv(envVal);

    // 比较两个副本
    if (wxEnv == bdEnv) {
        std::cout << "same" << std::endl;
    } else {
        std::cout << "not same" << std::endl;
    }
    ...
}

```
**【错误示例】**

```
如下示例是期望通过getenv函数取到TABLE_WX_ENV和TABLE_BD_ENV两个环境变量的值，再判断这两个值是否相同。但是由于getenv()是不可重入的，在第二次调用该函数时，可能会覆盖上一次取到的字符串内容，所以即使两个环境变量是不同的，但是最终两者wxEnv和bdEnv在比较时可能相同。

void Foo()
{
    char* wxEnv = getenv("TABLE_WX_ENV");
    if (wxEnv == nullptr) {
        ... // 错误处理
        return;
    }

    char* bdEnv = getenv("TABLE_BD_ENV");
    if (bdEnv == nullptr) {
        ... // 错误处理
        return;
    }

    if (strcmp(wxEnv, bdEnv) == 0) {
        std::cout << "same" << std::endl;
    } else {
        std::cout << "not same" << std::endl;
    }
}

```
**【修复建议】**

代码执行路径上，如果需要在第N(N>1)调用getenv后，访问第1~N-1次调用getenv返回指针所指向内容，需在连续调用的过程中，分配缓存区缓存上一次调用的返回结果。
