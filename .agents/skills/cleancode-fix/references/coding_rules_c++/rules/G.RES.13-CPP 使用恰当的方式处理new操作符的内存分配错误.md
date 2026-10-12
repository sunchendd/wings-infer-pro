# G.RES.13-CPP 使用恰当的方式处理new操作符的内存分配错误

- **规则ID**：fffee9c6-2824-4c5c-a39e-9b6ba674c223
- **更新时间**：2025-03-25 19:23:21

---

**【问题级别】**

一般

**【描述】**

默认的new操作符在内存分配失败时，会抛出std::bad_alloc异常，而使用了std::nothrow参数的new操作符在内存分配失败时，会返回nullptr。



因此，需要针对不同场景来处理new操作符的内存分配错误：



对于不会返回nullptr的new操作，不要对返回值做空指针检查

对于可能会返回nullptr的new操作，与对待malloc等内存分配函数一样，需要对返回值做空指针检查，如：使用了std::nothrow的new操作

**【正确示例】**

```
如下示例中，使用了std::nothrow参数的new操作符，必须对返回值做空指针检查。
void Fun()
{
    char* p = new(std::nothrow) char[BUFFER_SIZE];
    if (p == nullptr) {
        ... // 错误处理
    }
    ...
}

```
**【错误示例】**

```
如下代码中，如果new操作失败抛出异常，则不会执行到if语句及后面的代码，因此检查空指针是多余的操作。
void Fun()
{
    char* p = new char[BUFFER_SIZE];
    if (p == nullptr) {
        ... // 错误处理
    }
    ...
}

```
**【修复建议】**

C++ 的 new 操作符默认情况下，如果出现内存分配失败，会抛出 std::bad_alloc 异常，请进行异常捕获。或者可以使用 std::nothrow 版本的 new 操作符，使得它分配失败的时候不抛异常，而是返回nullptr，需要对返回值做判空检查。
