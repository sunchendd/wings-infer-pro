# G.CLS.12-CPP 在重写虚函数时应明确指定override或final

- **规则ID**：2f300a6e-32a0-4bd5-bef2-6b5a4e3d6dd7
- **更新时间**：2025-03-25 19:22:11

---

**【问题级别】**

严重

**【描述】**

在重写虚函数时明确指定override或final，能保证该函数是重写了基类的虚函数，并且无需再添加virtual关键字。如果派生类函数与基类函数原型不一致，则产生编译错误。final还保证虚函数不会再被派生类重写。



virtual 表示一个新的虚函数

override 表示重写了基类中的虚函数，可以再被派生类重写

final 表示重写了基类中的虚函数，不能再被派生类重写

指定了override或final后，如果修改了基类虚函数原型，但忘记修改派生类重写的虚函数，在编译时就可以发现。也可以避免有多个派生类时，重写虚函数的修改遗漏。

**【正确示例】**

```
class Base {
public:
    Base();
    virtual ~Base();
    virtual void Foo(int var);
    virtual void Foo();
    void Bar();
};

class Derived : public Base {
public:
    Derived();
    ~Derived() override;       // 符合：虚析构函数 添加 override
    void Foo(int var) final;   // 符合：重写基类函数，并且Derived的派生类不能再重写此函数
    void Foo() override;       // 符合：重写基类函数
    void Foo() const override; // 编译失败: Derived::Foo和Base::Foo原型不一致，不是重写
    void Bar() override;       // 编译失败: Base::Bar 不是虚函数
};

```
**【错误示例】**

```
auto?ila2{?10?};??????// std::initializer_list<int>

```
**【修复建议】**

重写虚函数时使用override或final关键字修饰
