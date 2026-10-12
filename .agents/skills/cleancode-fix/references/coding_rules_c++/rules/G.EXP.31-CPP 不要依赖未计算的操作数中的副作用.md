# G.EXP.31-CPP 不要依赖未计算的操作数中的副作用

- **规则ID**：341aeebc-231d-414c-b7e2-73e418a7c5e8
- **更新时间**：2025-03-25 19:23:16

---

**【问题级别】**

一般

**【描述】**

一些表达式的操作数在运行期不会被计算，也不会触发该操作数的副作用，如：sizeof、noexcept、decltype等。特别地，typeid表达式仅在其操作数为返回多态类型的引用的函数调用时，才会对操作数进行计算。



因此，不要依赖未计算的操作数中的副作用。

**【正确示例】**

```
在需要利用具有副作用的表达式生成有效代码并且不会发生副作用时，可以将该表达式作为未计算的操作数使用。

在C++11中，如下代码使用decltype(++std::declval<T&>())利用自增表达式的结果类型声明了函数的返回类型，没有发生副作用。

template <typename T>
std::remove_reference_t<decltype(++std::declval<T&>())> AllocateId()
{
    static T lastId{0};
    return ++lastId;
}

auto newId = AllocateId<std::atomic<uint32_t>>();
如下代码中，使用noexcept(a.swap(b))得到异常说明，没有发生副作用。

template <typename T>
void swap(T& a, T& b) noexcept(noexcept(a.swap(b)));

```
**【错误示例】**

```
如下代码中，typeid表达式中的副作用取决于操作数的类型，容易发生混淆。

class A {
public:
    A() = default;
    virtual ~A() = default;
    ...
};

class B {
public:
    B() = default;
    ~B() = default;
    ...
};

A& GetObjectARef();           // 返回A类型对象的引用，A为多态类
A GetObjectA();               // 返回A类型临时对象
B& GetObjectB();              // 返回B类型对象的引用，B不是多态类

typeid(GetObjectARef());      // 不符合：A为多态类，GetObjectRef会被调用
typeid(GetObjectA());         // 不符合：返回值不是引用，GetObjectA不会被调用
typeid(GetObjectB());         // 不符合：B不是多态类，GetObjectB不会被调用
如下代码中的data++不会发生自增，除非 data++ 的返回类型和 data 的类型不一致，否则此处表达式没有意义，应写成 sizeof(data) 或其他有意义的表达式。

int data = 0;

size_t size = sizeof(data++); // 不符合：data++没有发生自增
std::cout << data;

decltype(data++) value = 1;   // 不符合：data++没有发生自增
std::cout << data;

```
**【修复建议】**

不要向sizeof和typeid传递有副作用的操作数。
