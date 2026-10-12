# G.INC.05-CPP 禁止在extern "C"中包含头文件

- **规则ID**：f0deeb77-bcb6-4d75-9afd-3109ee246005
- **更新时间**：2025-03-25 19:22:52

---

**【问题级别】**

严重

**【描述】**

在 extern “C” 中包含头文件，有可能会导致 extern “C” 嵌套，部分编译器对 extern “C” 嵌套层次有限制，嵌套层次太多会编译错误。



在C，C++混合编程的情况下，在extern “C”中包含头文件，可能会导致被包含头文件的原有意图遭到破坏，例如链接规范被不正确地更改。

**【正确示例】**

```

#ifdef __cplusplus
#include "a.h" // 符合，不会有extern c嵌套
extern "C" {
#endif

void B(void);

#ifdef __cplusplus
}
#endif

```
**【错误示例】**

```
#ifdef __cplusplus
extern "C" {
#endif

#include "a.h" // 不符合，可能会出现嵌套
void B(void);

#ifdef __cplusplus
}
#endif

```
**【修复建议】**

修改include位置，避免出现extern "C"嵌套
