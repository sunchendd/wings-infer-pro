# G.FUN.04-CPP 避免定义C风格的变参函数

- **规则ID**：632f2daa-45c0-4a39-b963-2369fe9aad39
- **更新时间**：2025-03-25 19:22:01

---

**【问题级别】**

一般

**【描述】**

实现C风格的变参函数时，需要从va_arg中读取参数，而从va_arg中读取参数不会有任何类型检查，只能由程序员人工保证参数类型的正确性。



为了避免类型错误，应使用可变参数模板等其他方式来代替va_arg可变参数。

**【正确示例】**

```
void Log(int priority)
{
    std::cerr << priority << std::endl;
}

template <typename T, typename... Args>
constexpr void Log(int priority, T head, Args... tail)
{
    std::cerr << head << " ";
    Log(priority, tail...);
}

Log(INFO, "this is an error");          // 函数能正常工作

```
**【错误示例】**

```
void Log(int priority, ...)             // 不符合：定义了C风格的变参函数
{
    va_list ap;
    va_start(ap, priority);
    char* p = va_arg(ap, char*);        // 假设传入的类型是 char*，并且无法检查类型
    while (p != nullptr) {
        std::cerr << p << " ";
        p = va_arg(ap, char*);
    };
    std::cerr << priority << std::endl;
    va_end(ap);
}

Log(INFO, "this is an error", nullptr); // 函数能正常工作
Log(INFO, "this is an error");          // 最后一个参数不是 nullptr，产生非预期行为

```
**【修复建议】**

修改为C++风格变参函数
