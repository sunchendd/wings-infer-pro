# G.VAR.05 指向资源句柄或描述符的变量，在资源释放后立即赋予新值

- **规则ID**：9f090dba-8541-4c7b-8603-a9c1a5682b4b
- **更新时间**：2026-04-07 04:10:05

---

**【问题级别】**

严重

**【描述】**

指向资源句柄或描述符的变量包括指针、文件描述符、socket描述符以及其它指向资源的变量。



对于全局性或跨函数的指向资源的变量，在释放后应立即赋予新值，以避免发生使用已释放资源的安全问题。

对于仅在单个函数内可见的指向资源的变量，在资源释放后可以不赋予新值，但应确保不被再次使用。



以指针为例，如果操作悬空指针（dangling pointer），可能会导致双重释放内存或使用已释放内存的安全漏洞。消减该漏洞的一种方法是将释放后的指针立即设置为一个确定的新值，如NULL。

**【正确示例】**

```
如下代码示例中，立即对释放后的指针设置为NULL，避免重复释放指针。
int Func(void)
{
    SomeStruct *msg = NULL;
    int ret = 0;
    ... // 初始化msg->type，分配 msg->body 的内存空间
    if (msg->type == MESSAGE_A) {
        ...
        free(msg->body);
        msg->body = NULL;	// 符合
    }
    ...
    if (someError) {
        ...
        goto ERROR_EXIT;
    }
    // 将msg存入全局队列，后续可能使用已释放的body成员
    InsertMsgToQueue(msg);
    return ret;
ERROR_EXIT:
    ...
    free(msg->body); // 马上离开作用域，不必赋值NULL
    free(msg);       // 马上离开作用域，不必赋值NULL
    return ret;
}
当free()函数的入参为NULL时，函数不执行任何操作。

如下代码示例中，立即对释放后的指针设置为NULL，避免访问已释放内存。
void FreeSomeStruct(SomeStruct *p)
{
    if (p == NULL) {
        return;
    }
    if (p->content != NULL) {
        free(p->content);
        p->content = NULL;  // 有效的置空，避免后续操作
    }
    ...
    free(p);
}
void DoSomeThing(void)
{
    SomeStruct *p = AllocSomeStruct(...); // 分配结构体内存并初始化
    ...
    if (condition) {
        FreeSomeStruct(p);
        p = NULL;
    }
    if (p != NULL) {
        errno_t ret = memcpy_s(buf, sizeof(buf), p->content, p->contentLen);
        ...
    }
}


```
**【错误示例】**

```
如下代码示例中，根据消息类型处理消息，处理完后释放掉body指向的内存，但是释放后未将指针设置为NULL。如果还有其他函数再次处理该消息结构体时，可能出现重复释放内存或访问已释放内存的问题。

int Func(void)
{
    SomeStruct *msg = NULL;
    int ret = 0;

    ... // 分配msg，初始化msg->type，分配 msg->body 的内存空间

    if (msg->type == MESSAGE_A) {
        ...
        free(msg->body); // 不符合：释放内存后，未置空
    }
    ...
    if (someError) {
        ...
        goto ERROR_EXIT;
    }
    // 将msg存入全局队列，后续可能使用已释放的body成员
    InsertMsgToQueue(msg);
    return ret;
ERROR_EXIT:
    ...
    free(msg->body);  // 可能再次释放了body的内存
    free(msg);
    return ret;
}
如下代码示例中文件描述符关闭后未赋新值。

SOCKET s = INVALID_SOCKET;
int fd = -1;
...
closesocket(s);
...
close(fd);
...
如下代码示例中，FreeSomeStruct函数中释放p后设置NULL的操作是无效的，导致DoSomeThing函数访问已释放内存。

void FreeSomeStruct(SomeStruct *p)
{
    if (p == NULL) {
        return;
    }
    if (p->content != NULL) {
        free(p->content);
        p->content = NULL;
    }
    free(p);
    p = NULL;
}

void DoSomeThing(void)
{
    SomeStruct *p = ... // 分配结构体内存并初始化
    ...
    if (condition) {
        FreeSomeStruct(p);
    }
    if (p != NULL) {
        // 可能会访问已释放内存
        errno_t ret = memcpy_s(buf, sizeof(buf), p->content, p->contentLen);
        ...
    }
}

```
**【修复建议】**

对于全局性或跨函数的指向资源的变量，在释放后应立即赋予新值，以避免发生使用已释放资源的安全问题。

对于仅在单个函数内可见的指向资源的变量，在资源释放后可以不赋予新值，但应确保不被再次使用。
