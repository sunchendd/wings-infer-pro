# G.RES.11-CPP new和delete配对使用，new[]和delete[]配对使用

- **规则ID**：3233ebc2-18e1-4f4b-b5f4-257d7ba94aa2
- **更新时间**：2025-03-25 19:22:36

---

**【问题级别】**

严重

**【描述】**

使用new操作符创建的对象，只能由delete操作符来销毁。

使用new[]操作符创建的对象数组，只能由delete[]操作符来销毁。

**【正确示例】**

```
class C {
public:
    C(size_t len) : arr(new int[len]) {}

    ~C()
    {
        delete[] arr;
    }

private:
    int* arr;
};

```
**【错误示例】**

```
class C {
public:
    C(size_t len) : arr(new int[len]) {}

    ~C()
    {
        delete arr;                       // 不符合：此处应使用delete[]
    }

private:
    int* arr;
};

```
**【修复建议】**

使用相应的delete操作符
