# G.FUU.09 禁止使用realloc()函数

- **规则ID**：05a9b574-9dc2-4e9e-9a9b-9e3451573d3d
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

realloc()是一个非常特殊的函数，原型如下：



void *realloc(void *ptr, size_t size);

随着参数的不同，其行为也是不同：



当ptr不为NULL，且size不为0时，该函数会重新调整内存大小，并将新的内存指针返回，并保证最小的size的内容不变；

参数ptr为NULL，但size不为0，那么其行为等同于malloc(size)；

参数size为0，则realloc的行为等同于free(ptr)。

由此可见，一个简单的C函数，却被赋予了3种行为，这不是一个设计良好的函数。虽然在编程中提供了一些便利性，如果认识不足，使用不当，极易引发各种bug。

**【正确示例】**

```
使用malloc()函数代替realloc()函数。

// 使用malloc()函数代替realloc()函数
char *newPtr = (char *)malloc(NEW_SIZE);
if (newPtr == NULL) {
    ... // 错误处理
}

errno_t ret = memcpy_s(newPtr, NEW_SIZE, oldPtr, oldSize);

... // 校验ret，确保安全函数执行成功

... // 返回前，释放oldPtr

```
**【错误示例】**

```
如下代码示例中，使用realloc不当导致内存泄漏。
代码中ptr指向一段已经申请成功的内存，此时希望对ptr的空间进行扩充，当realloc()分配失败的时候，会返回NULL。但是参数中的ptr的内存是没有被释放的，如果直接将realloc()的返回值赋给ptr，那么ptr原来指向的内存就会丢失，造成内存泄漏。
...
char *ptr = ...;    // ptr指向一段已经申请成功的内存
ptr = (char *)realloc(ptr, NEW_SIZE); // 当realloc()分配内存失败时会返回NULL，导致内存泄漏
if (ptr == NULL) {
    ... // 错误处理
}

```
**【修复建议】**

参考规范http://openx.huawei.com/communityWikiDetails?communityId=41&ibid=SPE1000000103&navid=NVI1000001252
