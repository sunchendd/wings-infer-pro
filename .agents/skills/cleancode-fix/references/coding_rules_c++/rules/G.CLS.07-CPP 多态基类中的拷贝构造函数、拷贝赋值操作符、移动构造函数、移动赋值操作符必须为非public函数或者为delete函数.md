# G.CLS.07-CPP 多态基类中的拷贝构造函数、拷贝赋值操作符、移动构造函数、移动赋值操作符必须为非public函数或者为delete函数

- **规则ID**：d83fba05-26ce-4179-9a20-46f8d63dd75e
- **更新时间**：2025-03-25 19:22:08

---

**【问题级别】**

严重

**【描述】**

如果把一个派生类对象直接赋值给基类对象，会发生切片，只拷贝或者移动了基类部分，损害了多态行为。

**【正确示例】**

```
class Base {
public:
    Base() = default;
    virtual ~Base() = default;
    ...
    virtual void Fun() { std::cout << "Base" << std::endl; }
};

class Derived : public Base {
    ...
    void Fun() override { std::cout << "Derived" << std::endl; }
};

void Foo(const Base& base)
{
    Base other = base;     // 不符合：发生切片
    other.Fun();           // 调用的是Base类的Fun函数
}
Derived d;
Foo(d);                    // 传入的是派生类对象

```
**【错误示例】**

```
##### 场景1：把一个派生类对象直接赋值给基类对象导致切片。
- 错误示例：

```cpp
class Base {
public:
    Base() = default;
    virtual ~Base() = default;
    ...
    virtual void Fun() { std::cout << "Base" << std::endl; }
};

class Derived : public Base {
    ...
    void Fun() override { std::cout << "Derived" << std::endl; }
};

void Foo(const Base& base)
{
    Base other = base;  // 不符合：发生切片
    other.Fun();        // 调用的是Base类的Fun函数
}

void Func()
{
    Derived d;
    Foo(d);             // 传入的是派生类对象
}
```
##### 场景2：把一个派生类对象移动给基类对象导致切片。
- 错误示例：

```cpp
class Base {
public:
    Base() = default;
    virtual ~Base() = default;
    ...
    virtual void Fun() { std::cout << "Base" << std::endl; }
};

class Derived : public Base {
    ...
    void Fun() override { std::cout << "Derived" << std::endl; }
};

void Call()
{
    Derived d;              // 派生类对象
    Base b = std::move(d);  // 不符合：发生切片
    b.Fun();                // 调用的是Base类的Fun函数
}
```

```
**【修复建议】**

声明为非public或者delete
