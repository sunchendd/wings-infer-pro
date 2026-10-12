# G.CLS.09-CPP 在移动构造函数和移动赋值操作符中必须将源对象的资源正确重置

- **规则ID**：05b41de9-a7e7-4dc3-b6ea-27c66097961c
- **更新时间**：2025-03-25 19:23:08

---

**【问题级别】**

一般

**【描述】**

移动构造函数和移动赋值操作符将资源的所有权从一个对象移动到另外一个资源。一旦资源被移动，则应将源对象的资源正确重置。这样可以防止源对象在析构函数中释放了被移动的资源。



在被移动的对象中允许保留部分非资源相关数据，但必须保证被移动的对象处于可被正常析构的状态。

因此，当一个对象被move以后，除非该对象处于明确指定的状态，否则不要依赖已move对象的值，否则可能产生非预期行为。

**【正确示例】**

```
class Foo {
public:
    ...
    Foo(Foo&& other) noexcept : data(other.data)
    {
        other.data = nullptr;
    }
    Foo& operator=(Foo&& other) noexcept
    {
        if (this == &other) {
            return *this;
        }
        delete[] data;
        data = other.data;
        other.data = nullptr;
        return *this;
    }
    ~Foo()
    {
        delete[] data;
    }
private:
    char* data = nullptr;
};
此外，不要依赖已经被move对象的值。
某些标准库std::string的实现可能对短字节做优化，在实现移动语义时可能不会修改被移动字符串的内容，导致如下代码输出不一定是预期的b， 有可能输出为ab，存在兼容性问题。

std::string str{"a"};
std::string other = std::move(str);
str.append(1, 'b');
std::cout << str << std::endl;

```
**【错误示例】**

```
class Foo {
public:
    ...
    Foo(Foo&& other) noexcept : data(other.data) {}
    Foo& operator=(Foo&& other) noexcept
    {
        data = other.data;
        return *this;
    }
    ~Foo()
    {
        delete[] data;
    }
private:
    char* data = nullptr;
};
上述Foo的移动构造函数和移动赋值操作符没有正确将源对象的资源重置，源对象析构的时候会将资源释放，导致新创建的对象中接管的资源成为无效资源。

```
**【修复建议】**

移动构造函数和移动赋值操作符中应该将源对象的资源正确重置。
