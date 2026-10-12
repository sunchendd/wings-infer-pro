# SecA_FormatStringNumView

- **规则ID**：23875462-8e31-42d6-ba66-dfa63be11871
- **更新时间**：2025-03-25 19:23:52

---

**【问题级别】**

一般

**【描述】**

检查格式化函数使用时，格式化参数所要求的参数数量与实际参数数量不一致的场景。



**【正确示例】**

```
```cpp
#include <stdlib.h>
int Debug_Log(const char *buffer, size_t len, const char *format, ...) { return 0; }
void GoodCase01()
{
    char buffer[100] = "";
    int i = 1;
    unsigned char c = 2;
    int ret = Debug_Log(buffer, sizeof(buffer) - 1, "%s %5d %uc", "hello", i, c);
    if (ret == -1) {
        return;
    }
}
```


```
**【错误示例】**

```
```cpp
#include <stdlib.h>
int Debug_Log(const char *buffer, size_t len, const char *format, ...) { return 0; }
// true_negative SecBrella:SecA_FormatStringNumView
void BadCase01()
{
    int i = 1;
    int j = 1;
    char buffer[10] = "";
    // Debug_Log函数，"%-5d
 %kd" %kd不符合格式，只有%-5d需要1个可变参数
    int ret = Debug_Log(buffer, sizeof(buffer) - 1, "%-5d
 %kd", i, j);
    if (ret == -1) {
        return;
    }
}
```


```
**【修复建议】**

使用格式化函数时，实际传递的可变参数的数量要与格式化参数所要求的可变参数数量一致。
