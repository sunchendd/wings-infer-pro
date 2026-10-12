# G.VAR.08 资源不再使用时应予以关闭或释放（V5.2试点）

- **规则ID**：2af576ed-53b8-499a-b825-f994047a831a
- **更新时间**：2025-03-25 19:24:05

---

**【问题级别】**

一般

**【描述】**

这里的资源包括计算机内存、文件、进程、线程、信号量、socket等。程序员在创建或分配资源后，如果该资源不再被使用，程序员应将其正确的关闭或释放，尤其要注意所有可能的异常路径，避免遗漏。



以计算机内存为例，当动态分配内存不再使用时应予以释放，否则会发生内存泄漏，如果攻击者可以有意触发该漏洞，则内存资源可能被耗尽，造成拒绝服务。



以文件描述符为例，当打开的文件不再使用时应将指向该文件的描述符关闭，否则会发生该文件描述符泄漏，如果攻击者可以有意触发该漏洞，则可用的文件描述符可能被耗尽，造成拒绝服务。

**【正确示例】**

```
#define    BLOCK_SIZE_MAX    256

char *GetBlock(int fd)
{
    ...
    char *buf = (char *)malloc(BLOCK_SIZE_MAX);
    if (buf == NULL) {
        return NULL;
    }

    if (read(fd, buf, BLOCK_SIZE_MAX) != BLOCK_SIZE_MAX) {
        free(buf);  // 符合：在异常路径中返回前释放buf指向的内存资源，并立即将指针置空。
        buf = NULL;
    }
    return buf;
}

```
**【错误示例】**

```
#define BLOCK_SIZE_MAX    256

char *GetBlock(int fd)
{
    ...
    char *buf = (char *)malloc(BLOCK_SIZE_MAX);
    if (buf == NULL) {
        return NULL;
    }

    if (read(fd, buf, BLOCK_SIZE_MAX) != BLOCK_SIZE_MAX) {
        return NULL;  // 不符合：在异常路径中返回前未释放buf指向的内存资源，存在内存泄漏。
    }
    return buf;
}

```
**【修复建议】**

程序员在创建或分配资源后，如果该资源不再被使用，程序员应将其正确的关闭或释放，尤其要注意所有可能的异常路径，避免遗漏。
