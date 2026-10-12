# G.TMP.01-CPP 模板的所有部分和显式特殊化都必须放在该模板本身所在的文件中

- **规则ID**：e2460d55-dff0-4e0a-88d7-9a8e24a51acc
- **更新时间**：2025-03-25 19:23:22

---

**【问题级别】**

一般

**【描述】**

模板类的所有部分都必须放在同一个文件中定义 。模板是在使用的时候对函数、变量等进行实例化。因此，在实例化的时候，编译器必须能够看到该函数、变量的具体实现，否则会产生难以理解的编译、链接错误。如果这些定义分散在多个头文件中，用户include了一个头文件却没有include另一个头文件，就会很容易产生这类问题。



例如：如果模板类template <typename T> class Foo在头文件Foo.h中定义，那么它的所有成员变量（如int Foo::someVar）、成员函数（如void Foo::SomeMethod()）也都要在Foo.h中定义。



如果一个模板类、模板函数等对某个（或某些）类型参数特殊化了，那么，这些 所有的特殊化也都必须和这个模板类、函数等放在同一个文件中定义 。这个更重要，如果因为忘记include而导致编译器没有看到某个特殊化，那么编译器和链接器可能都不会报错，因为编译器仍然可以看到未特殊化的实现，这使得调试更加困难。而且，如果有的编译单元（.cpp）使用了这个特殊化，而另一个编译单元使用了未特殊化的实现，则有未定义行为。



例如：如果模板类template <typename T> class Bar在头文件Bar.h中定义，那么它对int的特殊化template <> class Bar<int>以及它对std::string的特殊化template <> class Bar<std::string>也都要在Bar.h中定义。

**【正确示例】**

```
这里Foo.h里声明了Foo的Run方法，却没有实现；定义了有实现的模板方法Bar。

// Foo.h
template <typename T>
class Foo {
public:
    void Run(T obj);
};

template <typename T>
void Bar(T obj)
{
    ...
}
但在同一个头文件中，实现了Foo<T>::Run；同时针对int类型对Bar进行了特殊化。

// Foo.h
template <typename T>
void Foo<T>::Run(T obj)
{
    ...
}

template <>
void Bar<int>(int obj)
{
    ...
}

#include "Foo.h"

int main()
{
    Foo<int> foo;
    foo.Run(0);   // 编译器找不到Foo<int>::Run(int)的实现

    Bar<int>(0);  // 编译器里看不到Foo2.h里特殊化的Bar<int>(int)

    return 0;
}

```
**【错误示例】**

```
这里Foo.h里声明了Foo的Run方法，却没有实现；定义了有实现的模板方法Bar。

// Foo.h
template <typename T>
class Foo {
public:
    void Run(T obj);
};

template <typename T>
void Bar(T obj)
{
    ...
}
但在另一个头文件中，实现了Foo<T>::Run；同时针对int类型对Bar进行了特殊化。

// Foo2.h
template <typename T>
void Foo<T>::Run(T obj)
{
    ...
}

template <>
void Bar<int>(int obj)
{
    ...
}
如果用户include了Foo.h却忘记了include Foo2.h，就会出错。

#include "Foo.h"

int main()
{
    Foo<int> foo;
    foo.Run(0);   // 编译器找不到Foo<int>::Run(int)的实现

    Bar<int>(0);  // 编译器里看不到Foo2.h里特殊化的Bar<int>(int)

    return 0;
}
需要将Foo.h和Foo2.h合并到同一个文件中，来解决这些问题。

```
**【修复建议】**

将模板的所有部分以及显式特殊化定义到同一文件中，对于类模板特殊化，如果特殊化参数为类，可以将模板针对该类的特殊化与该类的定义放到同一文件中。
