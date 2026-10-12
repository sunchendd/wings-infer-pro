# G.RES.14-CPP 避免出现delete this操作

- **规则ID**：f37515fa-02ec-4b94-851d-d21e591769fd
- **更新时间**：2025-03-25 19:23:21

---

**【问题级别】**

一般

**【描述】**

delete this操作是自己销毁自己，在此之后再访问到该对象的成员时，可能造成未定义行为。

**【正确示例】**

```
class SomeClass
{
public:
    SomeClass(){};
    ~SomeClass(){};
};

```
**【错误示例】**

```
class SomeClass
{
public:
    SomeClass(){};
    void destroy();
    ~SomeClass(){};
};
void SomeClass::destroy()
{
    /* ...do something... */
    delete this; // 错误！
}

```
**【修复建议】**

不使用delete this
