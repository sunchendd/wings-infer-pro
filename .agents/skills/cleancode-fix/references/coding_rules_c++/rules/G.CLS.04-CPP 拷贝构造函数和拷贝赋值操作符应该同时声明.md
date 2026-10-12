# G.CLS.04-CPP 拷贝构造函数和拷贝赋值操作符应该同时声明

- **规则ID**：10d4cbc1-9ea5-4136-87af-80e59cf21002
- **更新时间**：2025-03-25 19:22:06

---

**【问题级别】**

严重

**【描述】**

拷贝构造函数和拷贝赋值操作符都是具有拷贝语义的，应该同时声明，包括自定义实现、=default和=delete。

**【正确示例】**

```
// 同时出现
class Foo {
public:
    ...
    Foo(const Foo& other);
    Foo& operator=(const Foo& other);
    ...
};
// 同时=default
class Foo {
public:
    ...
    Foo(const Foo&) = default;
    Foo& operator=(const Foo&) = default;
    ...
};
// 同时=delete
class Foo {
public:
    ...
    Foo(const Foo&) = delete;
    Foo& operator=(const Foo&) = delete;
    ...
};

```
**【错误示例】**

```


```
**【修复建议】**

同时定义或者同时禁止拷贝构造函数和拷贝赋值操作符
