# G.CLS.03-CPP 单参数构造函数声明为explicit

- **规则ID**：da886fca-eb4a-4558-9b93-005785c8a193
- **更新时间**：2025-03-25 19:22:05

---

**【问题级别】**

一般

**【描述】**

可以通过单参数调用的构造函数以及自定义的类型转换函数，应该加上explicit声明，除非类的设计目就是需要隐式类型转换功能，否则可能会发生非预期的类型转换。



特别地，对于使用std::initializer_list作为参数的构造函数不加explicit声明，以便支持std::initializer_list的拷贝初始化。

**【正确示例】**

```
class Foo {
public:
    explicit Foo(const Point& point);      // 符合：单参数构造函数，加上explicit
    explicit Foo(int x, int y = 0);        // 符合：可以用单参数的构造函数，加上explicit

    Foo(const Foo& other);                 // 符合：拷贝构造函数，不加explicit
    Foo(Foo&& other);                      // 符合：移动构造函数，不加explicit

    explicit operator std::string() const; // 符合：自定义的类型转换函数，加上explicit

private:
    int x;
    int y;
};

void ProcessFoo(const Foo& foo) 
{
    std::string str = foo;                 // 编译失败
    ...
}

int main()
{
    ProcessFoo(0);                         // 编译失败
    return 0;
}

```
**【错误示例】**

```
##### 场景1：类的构造函数单参数时未添加explicit声明
- 错误示例：

```cpp
class MyTest {
public:
    MyTest(int Var);                    // 不符合
    MyTest(double Var, int VarDef = 0); // 不符合
    explicit MyTest(int *Var);
};
```

```
**【修复建议】**

添加explicit声明
