# G.RES.12-CPP 自定义new/delete操作符需要配对定义，且行为与被替换的操作符一致

- **规则ID**：469b4003-45cf-4fc8-9858-a59ccb078bb3
- **更新时间**：2025-03-25 19:22:45

---

**【问题级别】**

一般

**【描述】**

自定义操作符的时候，new和delete要配对定义，new[]和delete[]要配对定义。

自定义new/delete操作符的行为要与被替换的new/delete的行为一致。

**【正确示例】**

```
struct S {
    static void* operator new(size_t size)
    {
        ... // 自定义操作
        return ::operator new(size);
    }

    static void operator delete(void* ptr, size_t size)
    {
        ... // 自定义操作
        ::operator delete(ptr);
    }
};

```
**【错误示例】**

```
// 如果自定义了 operator new，必须同时自定义对应的 operator delete
struct S {
    static void* operator new(size_t size)
    {
        ... // 自定义操作
        return ::operator new(size);
    }
};

```
**【修复建议】**

// 如果自定义了 operator new，必须同时自定义对应的 operator delete

struct S {

    static void* operator new(size_t size)

    {

        ... // 自定义操作

        return ::operator new(size);

    }

};
