# G.CLS.11-CPP 在派生类中重写虚函数时禁止重新定义缺省参数值

- **规则ID**：6b6ac0ed-ae17-4e52-9e9d-aaac5389a3ae
- **更新时间**：2025-03-25 19:22:10

---

**【问题级别】**

严重

**【描述】**

在C++中，虚函数是动态绑定的，但函数的缺省参数却是在编译时就静态绑定的。这意味着最终执行的函数是一个定义在派生类，但使用了基类中的缺省参数值的虚函数。为了避免虚函数重载时，因参数声明不一致给使用者带来的困惑和由此导致的问题，虚函数重写时不要重新定义缺省参数值。

**【正确示例】**

```
##### 场景1：在派生类中重写虚函数时重新定义缺省参数值。
- 修复示例：

```cpp
class Base {
public:
    virtual ~Base() = default;
    virtual void Display(const std::string& text = "Base!") const
    {
        std::cout << text << std::endl;
    }
};

class Derived : public Base {
public:
    // 符合
    void Display(const std::string& text) const override
    {
        std::cout << text << std::endl;
    }
};
```

```
**【错误示例】**

```
class Base {
public:
    virtual ~Base() = default;
    virtual void Display(const std::string& text = "Base!") const
    {
        std::cout << text << std::endl;
    }
};

class Derived : public Base {
public:
    void Display(const std::string& text = "Derived!") const override
    {
        std::cout << text << std::endl; 
    }
};

int main()
{
    std::unique_ptr<Base> b = std::make_unique<Derived>();
    std::unique_ptr<Derived> d = std::make_unique<Derived>();

    b->Display();  // 程序输出结果: Base! 而期望输出：Derived!
    d->Display();  // 程序输出结果: Derived!
    return 0;
}

```
**【修复建议】**

派生类中的缺省参数值要与基类中的保持一致
