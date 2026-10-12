# G.EXP.14-CPP 使用由C++提供的类型转换操作

- **规则ID**：5c973d38-2871-44f9-b652-d9240970b1bf
- **更新时间**：2025-03-25 19:22:22

---

**【问题级别】**

严重

**【描述】**

C++提供的类型转换操作比C风格更有针对性，更易读，也更加安全，C++提供的转换有：



dynamic_cast：主要用于继承体系下行转换，该转换具有类型检查的功能。应做好基类和派生类的设计，合理使用dynamic_cast:

dynamic_cast的出现一般说明基类和派生类设计出现了问题，派生类破坏了基类的契约，不得不通过dynamic_cast转换到派生类进行特殊处理，这个时候更希望来改善类的设计，而不是通过dynamic_cast来解决问题。

如果强制转换不可避免，则应优先使用dynamic_cast，而不是使用static_cast，因为编译器将在运行时检查强制转换的有效性。

static_cast：和C风格转换相似可做值的强制转换，或上行转换(把派生类的指针或引用转换成基类的指针或引用)。如果是纯粹的算数转换，那么可以使用大括号初始化方式转换。

reinterpret_cast：用于转换不相关的类型，是一种不安全的转换，应尽量少用reinterpret_cast。

const_cast：用于移除对象的const属性，使对象变得可修改，这样会破坏数据的不变性，应尽量少用const_cast。

**【正确示例】**

```
##### 场景1：使用C风格强转，将基类转换为派生类
- 修复示例：

```cpp
class Base { ... };
class Derived : public Base { ... };

void Foo(Base *b)
{
    Derived *d = dynamic_cast<Derived *>(b);  // 符合：dynamic_cast 主要用于继承体系下行转换
}
```
##### 场景2：使用C风格的强转，将整型转换成另一种整型
- 修复示例：

```cpp
double a = 1.5;
int i = static_cast<int>(a); // 符合：static_cast 可做值的强制转换
```

```
**【错误示例】**

```
##### 场景1：使用C风格强转，将基类转换为派生类
- 错误示例：

```cpp
class Base { ... };
class Derived : public Base { ... };

void Foo(Base *b)
{
    Derived *d = (Derived *)b;  // 不符合：C风格强转，不安全
}
```
##### 场景2：使用C风格的强转，将整型转换成另一种整型
- 错误示例：

```cpp
double a = 1.5;
int i = (int)a; // 不符合
```

```
**【修复建议】**

将C类型转换替换为C++类型转换
