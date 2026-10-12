# G.STD.13-CPP 调用格式化输入/输出函数时，使用有效的格式字符串

- **规则ID**：fed7b030-a087-4765-af9f-cd603b3ed190
- **更新时间**：2025-03-25 19:23:38

---

**【问题级别】**

严重

**【描述】**

使用C风格的格式化输入/输出函数时，需要确保格式串是合法有效的，并且格式串与相应的实参类型是严格匹配的，否则会使程序产生非预期行为。



除C风格的格式化输入/输出函数以外，C++中类似的函数也需要确保使用有效的格式串，如C++20的std::format()函数。



对于自定义C风格的格式化函数，可以使用编译器支持的属性自动检查使用自定义格式化函数的正确性。例如：GCC支持自动检测类似printf, scanf, strftime, strfmon的自定义格式化函数，参考GCC手册的Common Function Attributes：



extern int CustomPrintf(void* obj, const char* format, ...)

    __attribute__ ((format (printf, 2, 3)));

**【正确示例】**

```
如下代码中，使用%hhx确保格式串与相应的实参类型严格匹配。

unsigned char macAddr[6];
...
// macStr中的数据格式为 e2:42:a4:52:1e:33
int ret = sscanf_s(macStr, "%hhx:%hhx:%hhx:%hhx:%hhx:%hhx
",
                  &macAddr[0], &macAddr[1],
                  &macAddr[2], &macAddr[3],
                  &macAddr[4], &macAddr[5]);
...
注：在C++中不推荐使用sscanf, sprintf等C库函数，可以替换为：std::istringstream, std::ostringstream, std::stringstream等。

```
**【错误示例】**

```
如下代码中，格式化输入一个整数到macAddr变量中，但是macAddr为unsigned char类型，而%x对应的是unsigned int类型参数，函数执行完成后会发生写越界。

unsigned char macAddr[6];
...
// macStr中的数据格式为 e2:42:a4:52:1e:33
int ret = sscanf_s(macStr, "%x:%x:%x:%x:%x:%x
",
                  &macAddr[0], &macAddr[1],
                  &macAddr[2], &macAddr[3],
                  &macAddr[4], &macAddr[5]);
...

```
**【修复建议】**

确保format函数参数个数和实际参数个数一致；确保指针变量用%p；确保宽度说明符、缓冲区长度参数使用正确。
