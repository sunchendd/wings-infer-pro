# G.CLS.10-CPP 通过基类指针释放派生类时，必须将基类中析构函数声明为虚函数

- **规则ID**：623a7165-8c39-4145-8bb7-dff0b4e68b3c
- **更新时间**：2025-03-25 19:22:09

---

**【问题级别】**

严重

**【描述】**

只有基类析构函数是虚函数时，才能保证通过多态调用的时候调用到派生类的析构函数。

如果没有将基类的析构函数声明为虚函数，当通过基类指针释放派生类时，只会调用基类的析构函数，不会调用派生类的析构函数，导致内存泄漏。

**【正确示例】**

```
##### 场景1：基类的析构函数声明为`非虚函数`，导致派生类数据的内存泄漏。
- 修复示例：

```cpp
class Base {
public:
    Base() = default;
    // 符合：基类的析构函数声明为`虚函数`
    virtual ~Base()
    {
        std::cout << "~Base" << std::endl;
    }
    virtual std::string GetVersion() = 0;
};

class Derived : public Base {
public:
    Derived()
    {
        constexpr size_t numberCount = 100;
        numbers = new int[numberCount];
    }

    // 在重写虚函数时应明确指定override或final
    ~Derived() override
    {
        delete[] numbers;
        std::cout << "~Derived" << std::endl;
    }

    std::string GetVersion() override
    {
        return std::string("hello!");
    }

private:
    int* numbers;
};

void Foo()
{
    Base* base = new Derived();
    delete base; // 先调用基类的析构函数，再调用派生类的析构函数，不存在内存泄漏
}
```

```
**【错误示例】**

```
没有将基类的析构函数声明为虚函数，导致了内存泄漏。

class Base {
public:
    Base() = default;
    ~Base() { std::cout << "~Base" << std::endl; }
    virtual std::string GetVersion() = 0;
};

class Derived : public Base {
public:
    Derived()
    {
        const size_t numberCount = 100;
        numbers = new int[numberCount];
    }

    ~Derived()
    {
        delete[] numbers;
        std::cout << "~Derived" << std::endl;
    }

    std::string GetVersion()
    {
        return std::string("hello!");
    }

private:
    int* numbers;
};

void Foo()
{
    Base* base = new Derived();
    delete base;                // 调用的是 Base 的析构函数，造成资源泄漏
}

```
**【修复建议】**

将基类析构函数声明为虚函数
