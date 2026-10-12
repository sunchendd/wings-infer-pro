# G.PRE.08 禁止宏调用参数中出现预编译指令

- **规则ID**：ba1cc67c-a89c-44d6-b9d0-80211a8e1981
- **更新时间**：2025-03-25 19:23:04

---

**【问题级别】**

严重

**【描述】**

这里的宏指函数式宏，其参数不能包括预处理器指令，如#include，#define和#ifdef，这样做会导致未定义的行为。



此规则还适用于在调用标准库函数参数的场景，因为任何标准库函数可作为宏来实现。

**【正确示例】**

```
#define WRITE_LOG(X)  printf("%s
", #X)
int Foo(void)
{
#ifdef PLATFORM1
    WRITE_LOG("Notice: Something error.");
#else
    WRITE_LOG("Code: 4567");
#endif
}

```
**【错误示例】**

```
如下代码可能会导致程序出现未定义行为。

#define WRITE_LOG(X)  printf("%s
", #X)
int Foo(void)
{
    WRITE_LOG(
#ifdef PLATFORM1
    "Notice: Something error."
#else
    "Code: 4567"
#endif
    );
}

```
**【修复建议】**

预处理指令在宏调用之外进行保护
