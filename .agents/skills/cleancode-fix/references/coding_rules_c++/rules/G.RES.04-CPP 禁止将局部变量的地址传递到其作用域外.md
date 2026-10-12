# G.RES.04-CPP 禁止将局部变量的地址传递到其作用域外

- **规则ID**：9b35e6df-b1f5-4b32-8842-bbf20d928c27
- **更新时间**：2025-03-25 19:23:20

---

**【问题级别】**

严重

**【描述】**

如果对象在其生命周期之外被引用，则程序会产生未定义行为。

**【正确示例】**

```
如下代码中，重构Fun函数的返回类型，使其返回一个整数值。

int Fun()
{
    int localVar = 0;
    ...
    return localVar;
}
一种修改方法是使用std::string作为函数的返回类型。

std::string GetData()
{
    constexpr char s[] = "hello world";
    return s;
}
或者使用std::string来取代字符串数组。

std::string GetData()
{
    std::string s{"hello world"};
    return s;
}

```
**【错误示例】**

```
如下代码中，Fun函数返回了局部变量的地址，在调用处解引用该指针时，程序会产生未定义行为。

int* Fun()
{
    int localVar = 0;
    ...
    return &localVar;                // 不符合：返回了局部变量地址  
}
如下代码中，使用std::string_view作为函数的返回类型，间接将局部变量地址返回到其作用域以外。

std::string_view GetData()
{
    const char s[] = "hello world";
    return s;                       // 不符合：会间接将s的地址返回到其作用域以外
}

```
**【修复建议】**

检查栈地址泄露的情况。使用静态变量或动态内存对该数据进行存储，并返回。检查函数结束后返回本地变量地址，告警

检查函数结束后函数内部的栈地址依旧存储在全局的或者堆空间中，告警
