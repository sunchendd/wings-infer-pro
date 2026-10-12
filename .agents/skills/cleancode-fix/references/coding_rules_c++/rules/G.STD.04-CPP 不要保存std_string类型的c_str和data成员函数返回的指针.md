# G.STD.04-CPP 不要保存std::string类型的c_str和data成员函数返回的指针

- **规则ID**：7605497d-89fc-4291-8a38-abf846844ef4
- **更新时间**：2025-03-25 19:22:59

---

**【问题级别】**

严重

**【描述】**

为保证调用std::string对象的c_str()和data()成员函数返回的引用值结果的有效性，不应保存std::string类型的c_str()和data()的结果，而是在每次需要时直接调用（调用的开销会被编译器内联优化）。否则，当调用此std::string对象的修改方法修改对象后，或超出std::string对象作用域时，之前存储的指针将会失效。使用失效的指针将导致未定义行为。

**【正确示例】**

```
void Foo1()
{
    std::string name{"demo"};

    name = "test";
    name[1] = '2';
    ...
    Bar(name.c_str());
}

void Foo2()
{
    std::string name{"demo"};
    std::string test{"test"};
    name += test;
    ...
    Bar(name.c_str());
}

void Foo3(std::string& s)
{
    ...
    s.replace(0, 3, "***");
    ...
    Bar(s.data());
}

```
**【错误示例】**

```
void Bar(const char* data)
{
    ...
}

void Foo1()
{
    std::string name{"demo"};
    const char* text = name.c_str();          // 表达式结束以后，name的生命周期还在，指针有效

    // 如果中间调用了std::string的非const成员函数，导致name被修改，例如operator[], begin()等，
    // 可能会导致text的内容不可用，或者不是原来的字符串
    name = "test";
    name[1] = '2';
    ...
    Bar(text);                                // 此处text已不再指向合法内存空间
}

void Foo2()
{
    std::string name{"demo"};
    std::string test{"test"};
    const char* text = (name + test).c_str(); // 表达式结束以后，+号产生的临时对象被销毁
    ...
    Bar(text);                                // 此处text已不再指向合法内存空间
}

void Foo3(std::string& s)
{
    const char* data = s.data();
    ...
    s.replace(0, 3, "***");
    ...
    Bar(data);                                // 此处text已不再指向合法内存空间
}

```
**【修复建议】**

直接使用函数c_str()和data()的返回值，而非保存返回值
