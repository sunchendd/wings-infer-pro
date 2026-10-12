# G.FUN.06-CPP 函数参数需传入单个对象时应以引用取代指针

- **规则ID**：50489c48-f65d-4e23-ab93-32958fea1f1f
- **更新时间**：2025-03-25 19:22:02

---

**【问题级别】**

一般

**【描述】**

引用比指针更安全，因为它一定非空，且一定不会再指向其他目标，不需要检查空指针。

**【正确示例】**

```
static void Foo(const SomeType& obj) // 符合： 使用引用取代指针
{
    ...
}

void Fun()
{
    SomeType obj;
    ...
    Foo(obj);
}

```
**【错误示例】**

```
static void Foo(const SomeType* obj) // 不符合： 当参数一定非空时应以引用取代指针
{
    ...
}

void Fun()
{
    SomeType obj;
    ...
    Foo(&obj);
}

```
**【修复建议】**

改成引用方式传参
