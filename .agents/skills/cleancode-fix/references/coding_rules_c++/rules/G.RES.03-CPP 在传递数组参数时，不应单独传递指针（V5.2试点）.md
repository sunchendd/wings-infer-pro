# G.RES.03-CPP 在传递数组参数时，不应单独传递指针（V5.2试点）

- **规则ID**：5f0c3050-5f7e-4d73-bfc6-b0bd0d36eb26
- **更新时间**：2025-03-25 19:24:04

---

**【问题级别】**

严重

**【描述】**

数组（不是数组的引用）或者指针作为函数参数时，未将其长度作为函数的参数，会导致函数内没有此入参指针的长度信息，无法判断内存的访问是否正确。

因此，为了避免数组作为函数参数时会导致的越界访问问题，必须同时传递其长度信息。

**【正确示例】**

```
场景1：数组作为函数参数时，其长度信息丢失。
- 修复示例1：如果函数接受的是不带长度的指针，那么应该把长度作为另外一个参数也传递进去。
int ParseMsg(unsigned char *msg, size_t msgLen)
{
    ASSERT(msg != nullptr);
    ASSERT(msgLen != 0);
    ...
}
void Func(void)
{
    unsigned char msg[MAX_MSG_LEN];
    ...
    ParseMsg(msg, sizeof(msg)); // 符合：将msg的大小作为参数传递到ParseMsg中
    ...
}

- 修复示例2：如果函数只接收固定长度的数组为参数，可以定义参数类型为数组引用。
int ParseMsg(unsigned char (&msg)[MAX_MSG_LEN])
{
    ...
}
void Func(void)
{
    unsigned char msg[MAX_MSG_LEN];
    ...
    ParseMsg(msg); // 符合：数组引用
    ...
}

- 修复示例3：如果函数只接收固定长度的数组为参数，可以定义参数类型为`std::array`（C++11）。
int ParseMsg(std::array<unsigned char, MAX_MSG_LEN> &msg)
{
    ...
}
void Func(void)
{
    std::array<unsigned char, MAX_MSG_LEN> msg;
    ...
    ParseMsg(msg); // 符合：std::array带长度信息，如果长度不同但逻辑一致可考虑用模板长度参数
}

- 修复示例4：如果函数只接收固定长度的数组为参数，可以定义参数类型为`std::span`（C++20）。
int ParseMsg(std::span<int> &mySpan)
{
    ...
}
void Func(void)
{
    unsigned char msg[MAX_MSG_LEN];
    std::span<int> mySpan(msg);
    ...
    ParseMsg(msg); // 符合：std::span带长度信息
}

- 修复示例5：可以把指针和长度合起来做成一个类型，方便统一场景使用。
// 可以把指针和长度合起来做成一个类型，方便统一场景使用
template <typename T>
class Slice {
public:
    template <size_t N> Slice(T (&arr)[N]) : data(arr), len(N) {}
    template <size_t N> Slice(std::array<T, N> arr) : data(arr.data()), len(N) {}
    Slice(T *arr, size_t n) : data(arr), len(n) {}
    ...
private:
    T *data;
    size_t len;
};

int ParseMsg(Slice<unsigned char> &msg)
{
    ...
}

void Func1(void)
{
    std::array<unsigned char, MAX_MSG_LEN> msg;
    Slice<unsigned char> s(msg);
    ParseMsg(s); // 符合
}

void Func2(void)
{
    unsigned char msg[MAX_MSG_LEN];
    Slice<unsigned char> s(msg);
    ParseMsg(s); // 符合
}

void Func3(void)
{
    unsigned char *p = new (std::nothrow) unsigned char[MAX_MSG_LEN];
    if (p == nullptr) {
        return;
    }
    Slice<unsigned char> s(p, MAX_MSG_LEN);
    ParseMsg(s); // 符合
    delete []p;
}

```
**【错误示例】**

```
场景1：数组作为函数参数时，其长度信息丢失。
- 错误示例：
int ParseMsg(unsigned char *msg)
{
    ASSERT(msg != nullptr);
    ...
}
void Func(void)
{
    unsigned char msg[MAX_MSG_LEN];
    ...
    ParseMsg(msg); // 不符合：函数ParseMsg不知道msg的范围，容易产生内存越界访问漏洞
    ...
}

```
**【修复建议】**

1. 如果函数只接收固定长度的数组为参数，可以定义参数类型为数组引用、`std::array`（C++11）或者`std::span`（C++20）。

2. 如果函数接受的是不带长度的指针，那么应该把长度作为另外一个参数也传递进去，并且长度参数需要紧跟在数组参数后面，如`int Foo(char *msg, size_t msgLen)`。

3. 对于const char *类型的参数，如果能确保'\0'不丢失，长度能够计算正确，不需要传长度参数。
