# G.ARR.06 不要使用变长数组类型

- **规则ID**：a584fb17-308a-4f05-8a30-59709b7ea1d5
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

变长数组是指在定义数组时，可以使用非const变量来指定数组的长度。

变长数组的数组长度不是固定的，是在运行时确认的，而不是在编译时，可能导致数组越界访问等安全问题。

因此，不要使用变长数组类型，建议使用定长数组或者申请动态内存。

**【正确示例】**

```
##### 场景1：使用变长数组，数组长度来自入参。
- 修复示例1：如果不能够明确数组大小，建议动态分配一段内存。

    ```c
    int ReadAndProcess(size_t n)
    {
        // 校验n是否合法
        ...
        // 符合：使用malloc分配大小
        int *array = (int *)malloc(n * sizeof(int));
        // array判空及初始化，此处略
        ...
    }
    ```
- 修复示例2：如果能够明确数组大小，建议显式指定其长度。

    ```c
    #define ARRAY_LEN 16
    int ReadAndProcess()
    {
        // 符合：明确array的大小，满足此处场景需求。
        int array[ARRAY_LEN];
        ...
    }
    ```
##### 场景2：使用变长数组，数组长度来自局部变量。
- 修复示例1：如果不能够明确数组大小，建议动态分配一段内存。

    ```c
    void Func()
    {
        size_t count = 10;
        // 符合：使用malloc分配大小
        int *array = (int *)malloc(count * sizeof(int));
        ...
    }
    ```
- 修复示例2：如果能够明确数组大小，建议显式指定其长度。

    ```c
    #define ARRAY_LEN 10
    int Func()
    {
        // 符合：明确array的大小，满足此处场景需求。
        int array[ARRAY_LEN];
        ...
    }
    ```
##### 场景3：使用变长数组作为入参。
- 修复示例1：如果不能够明确数组大小，建议动态分配一段内存。

    ```c
    void Func2(int *array, size_t n)
    {
        ...
    }
    void Bar(void)
    {
        size_t count = ...
        ...
        // 符合：动态申请一段内存
        int *array = (int *)malloc(count * sizeof(int));
        ...
        // 传入数组及其对应的size
        Func2(array, count);
        ...
    }
    ```
- 修复示例2：如果能够明确数组大小，建议显式指定其长度。

    ```c
    #define ARRAY_LEN 10
    void Func2(int *array, size_t n)
    {
        ...
    }
    void Bar(void)
    {
        // 符合：明确array的大小
        int array[ARRAY_LEN];
        ...
        // 传入数组及其对应的size
        Func2(array, sizeof(array));
        ...
    }
    ```


```
**【错误示例】**

```
##### 场景1：使用变长数组，数组长度来自入参。
- 错误示例：

    ```c
    int ReadAndProcess(size_t n)
    {
        int array[n]; // 不符合：使用变长数组类型
        ...
    }
    ```
##### 场景2：使用变长数组，数组长度来自局部变量。
- 错误示例：

    ```c
    void Func()
    {
        size_t count = 10;
        int array[count]; // 不符合: 使用变长数组类型
        ...
    }
    ```
##### 场景3：使用变长数组作为入参。
- 错误示例：

    ```c
    // 不符合: 该声明中的 array 会被调整为指针参数, 并不代表 array 的大小是 n
    void Func2(int n, int array[n])
    {
        ...
    }
    ```


```
**【修复建议】**

根据业务场景使用定长数组或者申请动态内存。

1. 如果不能够明确数组大小，建议动态分配一段内存。

2. 如果能够明确数组大小，建议显式指定其长度。
