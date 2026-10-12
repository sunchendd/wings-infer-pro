# G.RES.07-CPP 指向资源句柄或描述符的变量，在资源释放后立即赋予新值

- **规则ID**：5d8aaf39-fa82-44aa-9db6-bd168c6c6bc0
- **更新时间**：2025-03-25 19:24:16

---

**【问题级别】**

严重

**【描述】**

“指向资源句柄或描述符的变量”包括：指针、文件描述符、socket描述符以及其他指向资源的变量。



以指针为例，当指针成功申请了一段内存之后，在这段内存释放以后，如果其指针未立即设置为nullptr，也未分配一个新的对象，那这个指针就是一个悬空指针。

如果再对悬空指针操作，可能会发生重复释放或访问已释放内存的问题，造成安全漏洞。消减该漏洞的有效方法是将释放后的指针立即设置为一个确定的新值，例如：设置为nullptr。



对于全局性的资源句柄或描述符，在资源释放后，应该马上设置新值，以避免使用其已释放的无效值；对于只在单个函数内使用的资源句柄或描述符，应确保资源释放后其无效值不被再次使用。

**【正确示例】**

```
如下代码中，立即对释放后的指针设置为nullptr，避免重复释放指针。

int Fun()
{
    SomeStruct *msg = ...         // 使用new分配msg、msg->body的内存空间并初始化msg
    if (msg->type == MESSAGE_A) {
        ...
        delete msg->body;
        msg->body = nullptr;
    }
    ... 
    if (!InsertMsgToQueue(msg)) { // 将msg存入全局队列
        delete msg->body;         // 马上离开作用域，不必赋值 nullptr
        delete msg;               // 马上离开作用域，不必赋值 nullptr
        return -1;
    }
    return 0;
}
注：默认的内存释放函数针对空指针不执行任何动作。

如下代码中，在资源释放后，对应的变量应该立即赋予新值。

Socket s = INVALID_SOCKET;
int fd = -1;
...
CloseSocket(s);
s = INVALID_SOCKET;
...
close(fd);
fd = -1;
...

```
**【错误示例】**

```
如下代码中，根据消息类型处理消息，处理完后释放掉body指向的内存，但是释放后未将指针设置为nullptr。如果还有其他函数再次处理该消息结构体时，可能出现重复释放内存或访问已释放内存的问题。

int Fun()
{
    SomeStruct *msg = ...         // 使用new分配msg、msg->body的内存空间并初始化msg
    if (msg->type == MESSAGE_A) {
        ...
        delete msg->body;         // 不符合：释放内存后，未置空
    }
    ...
    if (!InsertMsgToQueue(msg)) { // 将msg存入全局队列，后续可能使用已释放的body成员
        delete msg->body;         // 可能重复释放了body的内存
        delete msg;
        return -1;
    }
    return 0;
}

如下代码中，文件描述符关闭后未赋新值。

Socket s = INVALID_SOCKET;
int fd = -1;
...
CloseSocket(s);
...
close(fd);
...

```
**【修复建议】**

参考规范http://openx.huawei.com/communityWikiDetails?communityId=41&ibid=SPE1000000176&navid=NVI1000004473
