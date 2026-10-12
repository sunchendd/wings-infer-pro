# G.ERR.07-CPP 在构造函数的函数级try-catch的catch块内，不能使用基类以及成员变量

- **规则ID**：cdaef64c-7d35-4830-ab26-a17bfcad4ecc
- **更新时间**：2025-03-25 19:22:42

---

**【问题级别】**

严重

**【描述】**

构造函数的函数级try-catch语句（见下面实例）一般用于处理基类和成员变量的初始化中抛出的异常。当执行到函数级的catch块时，所有已经被完全构造的基类和成员变量都已经被破坏（destroy，指的是它们占用的存储空间已经不存在了，不能被访问了），当然，没有完全构造的基类和成员也是不能被访问的。因此不能在catch中访问基类以及（包括基类和当前类的）成员变量。

**【正确示例】**

```
class Bar {
    int y;
    Evil evil;
public:
    Bar(int newX, int newY) try : Foo(newX), y(newY), evil(666) {
        ...
    } catch (...) {
        // 可以访问函数参数
        Log("Error happened when constructing Bar with", newX, "and", newY);
        throw;
    }
};

```
**【错误示例】**

```
class Evil {
public:
    Evil(int n)
    {
       throw SomeException();
    }
};

class Foo {
protected:
    int x;
public:
    Foo(int newX) : x(newX)
    {
    }
};

class Bar : public Foo {
    int y;
    Evil evil;
public:
    Bar(int newX, int newY) try : Foo(newX), y(newY), evil(666) {
        ...
    } catch (...) {
        Use(x);     // x已经被破坏
        Use(y);     // y已经被破坏
        Use(evil);  // evil还没完成构造
        throw;
    }
};

```
**【修复建议】**

在构造函数的函数级try-catch的catch块内，不要使用基类以及成员变量
