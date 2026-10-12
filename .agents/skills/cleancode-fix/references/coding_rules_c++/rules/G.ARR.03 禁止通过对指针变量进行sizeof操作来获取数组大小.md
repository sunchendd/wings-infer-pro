# G.ARR.03 禁止通过对指针变量进行sizeof操作来获取数组大小

- **规则ID**：fb8dfd25-28ab-4c63-9e9c-2726e32d9833
- **更新时间**：2025-03-25 19:23:36

---

**【问题级别】**

严重

**【描述】**

1. 当将`sizeof`应用于数组类型的函数参数时，sizeof操作符将得出指针类型的大小而非数组的实际大小，导致计算结果不符合预期，因此禁止通过对数组类型的函数参数变量进行`sizeof`来获取数组大小。



2. 将指针当做数组进行`sizeof`操作时，`sizeof`操作符将得出指针类型的大小而非数组的实际大小，会导致实际的执行结果与预期不符，因此禁止通过对指针变量进行`sizeof`操作来获取数组大小。

**【正确示例】**

```
##### 场景1：对数组类型的函数参数变量进行sizeof操作
- 修复示例1：

```cpp
void SizeofPointerCase01Bad01(int arr[], size_t length)
{
    /* POTENTIAL FLAW GOOD: 不使用sizeof,直接将数组长度当成入参传入 */
    for (size_t i = 0; i < length; i++) {
        arr[i] = i;
    }
}
void Entry(void)
{
    int arr[10];
    SizeofPointerCase01Bad01(arr, 10);
}
```
##### 场景2：对指针变量进行sizeof操作
- 修复示例1：

```cpp
void SizeofPointerCase02Good01()
{
    char *buffer = new(std::nothrow) char[BUFF_SIZE];
    if (buffer == nullptr) {
        return;
    }

    /* POTENTIAL FLAW GOOD: sizeof指针的类型并且乘以缓冲区长度 */
    memset_s(buffer, sizeof(char) * BUFF_SIZE, 0, sizeof(char) * BUFF_SIZE);

    delete[] buffer;
}
```

```
**【错误示例】**

```
##### 场景1：对数组类型的函数参数变量进行sizeof操作
- 错误示例1：

```cpp
void SizeofPointerCase01Bad01(int arr[])
{
    /* POTENTIAL FLAW: 对数组类型的函数参数变量进行sizeof操作 */
    for (int i = 0; i < sizeof(arr) / sizeof(arr[0]); i++) {
        arr[i] = i;
    }
}
void Entry(void)
{
    int arr[10];
    SizeofPointerCase01Bad01(arr);
}
```
##### 场景2：对指针变量进行sizeof操作
- 错误示例1：

```cpp
void SizeofPointerCase02Bad01()
{
    char *buffer = new(std::nothrow) char[BUFF_SIZE];
    if (buffer == nullptr) {
        return;
    }

    /* POTENTIAL FLAW: 对指针变量进行sizeof操作 */
    memset_s(buffer, sizeof(buffer), 0, BUFF_SIZE);

    delete[] buffer;
}
```

```
**【修复建议】**

- 对于数组类型的函数参数，应该通过传递其长度的方式，形如`void ArrayInit(int inArray[], size_t len)`。

- 对于指针变量，不能通过sizeof获取该指针指向的内存大小，应该通过上文确认指针指向的内存大小。
