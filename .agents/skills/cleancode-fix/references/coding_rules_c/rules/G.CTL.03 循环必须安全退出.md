# G.CTL.03 循环必须安全退出

- **规则ID**：07a09035-d88f-4e0a-9013-27c71d8a848a
- **更新时间**：2026-04-07 04:10:05

---

**【问题级别】**

一般

**【描述】**

在应用程序中，一个重复提供服务的逻辑循环应当设计退出机制，并且将资源正确释放后安全退出。退出条件的设计，除了让程序逻辑更加完整，也能通过实现优雅退出的代码，显式释放服务循环中分配的资源，避免资源泄漏。

**【正确示例】**

```
重新设计函数，通过提供服务退出条件，并在资源释放函数ReleaseServiceResource内释放服务循环前申请的资源。

bool ParseMsg(unsigned char *msg, size_t msgLen)
{
    ...
    if (msg->type == EXIT_MESSAGE_TYPE) {
        return false;
    } else {
        return true;
    }
}

void DoService(void)
{
    ...
    size_t size = 0;
    unsigned char *pMsg = NULL;
    bool doRunServiceFlag = true;    // 服务退出条件

    CreateServiceResource(); // 分配服务资源
    while (doRunServiceFlag) {
        pMsg = ReceiveMsg(&size);
        if (pMsg != NULL) {
            doRunServiceFlag = ParseMsg(pMsg, size);
            FreeMsg(pMsg);
        }
        size = 0;
    }
    ReleaseServiceResource(); // 释放服务资源
}

```
**【错误示例】**

```
以下代码，在一个大循环内，ReceiveMsg函数内申请资源，接收外部数据。ParseMsg函数内处理数据，但没有退出条件，会导致循环前申请的资源无法释放，该程序没有安全退出。

...
void DoService(void)
{
    ...
    size_t size = 0;
    unsigned char *pMsg = NULL;
    CreateServiceResource(); // 分配服务资源
    while (true) {
        pMsg = ReceiveMsg(&size);
        if (pMsg != NULL) {
            ParseMsg(pMsg, size);
            FreeMsg(pMsg);
        }
        size = 0;
    }
}

```
**【修复建议】**

在应用程序中，一个重复提供服务的逻辑循环应当设计退出机制，并且将资源正确释放后安全退出。退出条件的设计，除了让程序逻辑更加完整，也能通过实现优雅退出的代码，显式释放服务循环中分配的资源，避免资源泄漏。
