# G.FUD.07 数组作为函数参数时，必须同时将其长度作为函数的参数（V5.3试点）

- **规则ID**：132be147-666b-49b1-b37f-83da60e139e6
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

严重

**【描述】**

数组（不仅局限为数组类型变量，还包括字符串和指向连续内存块的指针）作为函数参数时，未将其长度作为函数的参数，会导致函数内没有此入参指针的长度信息，无法判断内存的访问是否正确。

因此，为了避免数组作为函数参数时会导致的越界访问问题，必须同时将其长度作为函数的参数。

**【正确示例】**

```
##### 场景1：动态申请的内存指针作为函数参数时，未将其长度作为函数的参数。
- 修复示例：使用数组作为函数参数时，同时将其参数作为函数的参数。

```c
int ParseMsg(unsigned char *msg, size_t msgLen)
{
    ASSERT(msg != NULL);
    ASSERT(msgLen != 0);
    ...
}

void Func(void)
{
    size_t len = GetMsgLen();
    ...
    unsigned char *msg = (unsigned char *)malloc(len);
    ...
    ParseMsg(msg, len); // 符合：将msg的大小作为参数传递到ParseMsg中
    ...
}
```
##### 场景2：固定长度的数组作为函数参数时，未将其长度作为函数的参数。
- 修复示例：使用数组作为函数参数时，同时将其参数作为函数的参数。

```c
int ParseMsg(unsigned char *msg, size_t msgLen)
{
    ASSERT(msg != NULL);
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
```

```
**【错误示例】**

```
##### 场景1：动态申请的内存指针作为函数参数时，未将其长度作为函数的参数。
- 错误示例：

```c
int ParseMsg(unsigned char *msg)
{
    ...
}

void Func(void)
{
    size_t len = GetMsgLen();
    ...
    unsigned char *msg = (unsigned char *)malloc(len);
    ...
    ParseMsg(msg); // 不符合：函数ParseMsg不知道msg的范围，容易产生内存越界访问漏洞
    ...
}
```
##### 场景2：固定长度的数组作为函数参数时，未将其长度作为函数的参数。
- 错误示例：

```c
int ParseMsg(unsigned char *msg)
{
    ASSERT(msg != NULL);
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

```
**【修复建议】**

使用数组作为函数参数时，同时将其长度作为函数的参数，并且长度参数需要紧跟在数组参数后面，如`int Foo(char *msg, size_t msgLen)`。

对于const char *类型的参数，如果能确保'\\0'不丢失，长度能够计算正确，不需要传长度参数。
