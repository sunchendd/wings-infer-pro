# G.RES.09-CPP 使用`std::make_unique`而不是`new`创建`std::unique_ptr`

- **规则ID**：8f398cff-c7bc-496b-95f5-b58536d4fbf4
- **更新时间**：2025-03-25 19:22:34

---

**【问题级别】**

严重

**【描述】**

本条款适用于C++14及之后的版本。C++14开始增加了std::make_unique，提供与std::make_shared类似的方式构造unique_ptr。



相对于先 new 出裸指针再构造 unique_ptr ，直接使用 make_unique 的优点有：



make_unique 可以更明确的避免裸指针和智能指针混用。

使用 make_unique 更简洁。

**【正确示例】**

```
void Foo()
{
    std::unique_ptr<C> sp = std::make_unique<C>(); // 符合
    ...                                            // 代码中只能使用 sp
}

```
**【错误示例】**

```
void Foo()
{
    C* p = new C();
    std::unique_ptr<C> sp = std::unique_ptr<C>(p); // 不符合
    ...                                            // 代码中既可以使用 p 也可以使用 sp
}

```
**【修复建议】**

使用std::make_unique来构造unique_ptr
