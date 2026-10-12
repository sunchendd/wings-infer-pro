# G.CLS.05-CPP 移动构造函数和移动赋值操作符应该同时声明

- **规则ID**：26e39d5c-3f96-48c0-b029-5a34e1f1fd3e
- **更新时间**：2025-03-25 19:22:07

---

**【问题级别】**

严重

**【描述】**

如果需要某个类支持移动操作，那么需要实现移动构造函数和移动赋值操作符。



移动构造函数和移动赋值操作符都是具有移动语义的，应该同时声明，包括自定义实现、=default和=delete。

**【正确示例】**

```
// 同时出现
class Foo {
public:
    ...
    Foo(Foo&& other);
    Foo& operator=(Foo&& other);
    ...
};
// 同时=default
class Foo {
public:
    ...
    Foo(Foo&&) = default;
    Foo& operator=(Foo&&) = default;
    ...
};
// 同时=delete
class Foo {
public:
    ...
    Foo(Foo&&) = delete;
    Foo& operator=(Foo&&) = delete;
    ...
};
class Foo {
public:
    ...
    Foo(Foo&& other);
    Foo& operator=(Foo&&) = delete;
    ...

private：
    const std::vector<std::string>& value;
};

```
**【错误示例】**

```


```
**【修复建议】**

同时声明移动构造函数和移动赋值操作符
