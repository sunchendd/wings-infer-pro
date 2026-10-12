# G.CLS.12-CPP 在重写虚函数时应明确指定override或final（V5.2试点）

- **规则ID**：5019b72a-0b6e-4d8f-962e-1ed57b396303
- **更新时间**：2025-03-25 19:21:40

---

**【问题级别】**

严重

**【描述】**

在重写虚函数时明确指定`override`或 `final`，如果派生类中重写的虚函数原型和基类的不一致，在编译时就可以发现。

**【正确示例】**

```
场景1：派生类中没有明确是重写虚函数，且函数原型和基类不一样，导致“重定义”基类的虚函数
- 修复示例：
class Base {
public:
    virtual void Func1()
    {
        std::cout << "Base::Func1" << std::endl;
    }
};

class Derived1 : public Base {
public:
    // 如果是"void Func1() const override", 编译会报错两个函数原型不一样，不是重写
    void Func1() override // 符合：明确指定override或final，且函数原型保持和基类一致
    {
        std::cout << "Derived1::Func1" << std::endl;
    }
};

class Derived2 : public Base {
public:
    void Func1() override // 明确重写虚函数
    {
        std::cout << "Derived2::Func1" << std::endl;
    }
};

int main()
{
    Base *d1 = new Derived1();
    Base *d2 = new Derived2();
    d1->Func1(); // 输出"Derived1::Func1"
    d2->Func1(); // 输出"Derived2::Func1"
    return 0;
}

```
**【错误示例】**

```
场景1：派生类中没有明确是重写虚函数，且函数原型和基类不一样，导致“重定义”基类的虚函数
- 错误示例：
class Base {
public:
    virtual void Func1()
    {
        std::cout << "Base::Func1" << std::endl;
    }
};

class Derived1 : public Base {
public:
    // 不符合：没有明确指定override或final，且函数原型和基类不一样，导致“重定义”基类的虚函数而不是“重写”
    void Func1() const
    {
        std::cout << "Derived1::Func1" << std::endl;
    }
};

class Derived2 : public Base {
public:
    void Func1() override // 明确重写虚函数
    {
        std::cout << "Derived2::Func1" << std::endl;
    }
};

int main()
{
    Base *d1 = new Derived1();
    Base *d2 = new Derived2();
    d1->Func1(); // 输出"Base::Func1"，因为Derived1是重定义而不是重写Func1，所以未实现多态
    d2->Func1(); // 输出"Derived2::Func1"
    return 0;
}

```
**【修复建议】**

在派生类重写虚函数时：

1. 无需再添加`virtual`关键字。

2. 明确指定`override`或`final`。

    - `override` 表示重写了基类中的虚函数，可以再被派生类重写

    - `final`    表示重写了基类中的虚函数，不能再被派生类重写

3. 函数原型保持和基类一致。
