# G.EXP.12-CPP 禁止逐位操作非`trivially copyable`对象

- **规则ID**：3b739e1f-f1a6-4fa4-bb5f-6730ad231b18
- **更新时间**：2025-03-25 19:22:22

---

**【问题级别】**

严重

**【描述】**

C++11中引入了trivially copyable的概念，允许使用memcpy、memset、memmove等函数逐位操作trivially copyable对象，但是操作的对象不能是potentially-overlapping subobject。



非trivially copyable对象中可能含有编译器生成的隐藏数据（如：虚表指针），如果逐位操作这些对象，可能会破坏对象的内部数据，造成严重问题。因此必须禁止逐位操作非trivially copyable对象。



此外，在存储对象的内存中也可能存在不属于表示该对象值的填充数据，这些数据可能是非预期的。即使在trivially copyable对象中，也可能存在填充数据，此时如果使用memcmp等函数比较它们，将得不到预期的结果。应优先使用特殊成员函数或重载操作符完成类对象的复制、赋值、比较等操作，避免直接逐位操作类对象。



满足trivially copyable的类型主要包括：



算数类型，如：bool、char、int、 float、double等

枚举类型

指针类型

满足trivially copyable的类。一般来说该类中没有虚函数或虚基类；类的非静态成员变量满足trivially copyable；类的析构函数不是自定义的；至少有一个有效的拷贝构造函数、拷贝赋值操作符、移动构造函数或移动赋值操作符，并且这些函数都不是自定义的。详见C++语言标准中对“trivially copyable class”的描述

上面这些类型的数组

potentially-overlapping subobject指的是：



基类子对象（base class subobject）

使用[[no_unique_address]]属性声明的非静态成员变量（C++20）

**【正确示例】**

```
##### 场景1：用memcpy_s复制了非trivially copyable对象
- 修复示例：

```cpp
class Point {
public:
    virtual void Fun() {};
    ...

private:
    int x = 0;
    int y = 0;
};

void Foo()
{
    Point a;
    Point b = a; // 符合
    ...
}
```

```
**【错误示例】**

```
如下代码中，Point不满足trivially copyable的要求。

class Point {
public:
    virtual void Fun() {};
    ...

private:
    int x = 0;
    int y = 0;
};

void Foo() {
    Point a;
    Point b;

    memcpy(&a, &b, sizeof(Point)); // 不符合：复制了非trivially copyable对象
    ...
}

```
**【修复建议】**

使用构造函数或赋值构造函数来进行初始化或赋值
