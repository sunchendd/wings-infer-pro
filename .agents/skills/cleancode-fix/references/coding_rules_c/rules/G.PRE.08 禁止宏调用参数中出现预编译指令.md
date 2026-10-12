# G.PRE.08 禁止宏调用参数中出现预编译指令

- **规则ID**：70db46ca-a5c0-4892-a47f-0c722ed64e8b
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

严重

**【描述】**

函数式宏的参数不能包括预处理器指令，如#include，#define和#ifdef，这样做会导致未定义的行为。

**【正确示例】**

```
##### 场景1：宏调用参数中出现预编译指令`#ifdef`
- 修复示例：

```c
#define WRITE_LOG(X)  printf("%s
", #X)

int Foo(void)
{
#ifdef PLATFORM1
    WRITE_LOG("Notice: Something error.");  // 符合：改为在每个预编译指令下均调用一次宏
#else
    WRITE_LOG("Code: 4567");                // 符合
#endif
}
```
##### 场景2：宏调用参数中出现预编译指令`#define`
- 修复示例：

```c
#define WRITE_LOG(X)  printf("%s
", #X)
#define ERR_INFO "Notice: Something error." // 宏在函数外定义

int Foo(void)
{
    WRITE_LOG(ERR_INFO); // 符合
    ...
}
```


```
**【错误示例】**

```
##### 场景1：宏调用参数中出现预编译指令`#ifdef`
- 错误示例：

```c
#define WRITE_LOG(X)  printf("%s
", #X)

int Foo(void)
{
    // 不符合：宏调用参数中出现预编译指令
    WRITE_LOG(
#ifdef PLATFORM1
    "Notice: Something error."
#else
    "Code: 4567"
#endif
    );
}
```
##### 场景2：宏调用参数中出现预编译指令`#define`
- 错误示例：

```c
#define WRITE_LOG(X)  printf("%s
", #X)

int Foo(void)
{
    // 不符合：宏调用参数中出现预编译指令
    WRITE_LOG(
#define ERR_INFO "Notice: Something error."
        ERR_INFO
    );
    ...
}
```


```
**【修复建议】**

宏参数不要出现预编译指令，可改为在每个预编译指令下均调用一次宏。
