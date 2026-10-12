# G.FUU.22 避免使用atoi、atol、atoll、atof函数

- **规则ID**：b4095192-ae1a-4796-a519-e8b4f796fe48
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

如果使用atoi()、atol()、atoll()、atof()系列函数将字符串转换为数值时，当字符串转换的结果无法表示成相应的数值时，会导致程序产生未定义行为，且无法判断转换过程中是否存在错误。



因此，避免使用atoi、atol、atoll、atof函数。

**【正确示例】**

```
##### 场景1：atol()函数无法判断转换过程中是否存在错误。
- 修复示例：使用strtol()、strtoll()、strtod()系列函数，并对endPtr、返回值及其errno的错误场景进行检查。

    ```c
    #define NUMBER_BASE 10
    void Func(const char *input)
    {
        char *endPtr = NULL;
        long result = 0;

        if (input == NULL) {
            return;
        }

        errno = 0;
        result = strtol(input, &endPtr, NUMBER_BASE); // 符合
        /*
        * 调用者可以通过检查 endPtr 的值和内容，来判断是否转换完全，
        * 可以通过 errno 是否为 ERANGE来判断是否超出整数表示范围
        */
        if (endPtr == input || *endPtr != '\0') {
            ... // 错误处理
        } else if ((result == LONG_MIN || result == LONG_MAX) &&
                (errno == ERANGE)) {
            ... // 错误处理
        }

        ...
    }
    ```


```
**【错误示例】**

```
##### 场景1：atol()函数无法判断转换过程中是否存在错误。
- 错误示例：

    ```c
    void Func(const char *input)
    {
        long result;
        if (input == NULL) {
            ... // 错误处理
        }

        /*
        * 不符合：当字符串不是以数字开始时，函数返回 0，并且不会设置errno值，调用者无法判断是否存在错误
        * 当字符串中间存在非数字字符时，函数返回已转换的数字，调用者无法判断是否完全转换
        * 当字符串中的数字超出目标类型表示范围时，程序会产生未定义行为，调用者无法判断是否存在错误
        */
        result = atol(input);
        ...
    }
    ```


```
**【修复建议】**

可以使用strtol()、strtoll()、strtod()系列函数代替atoi、atol、atoll、atof等函数相同的功能，并根据自身的业务设计函数的错误检查的代码。
