# G.FUU.12 正确设置安全函数中的destMax参数（V5.3试点）

- **规则ID**：b380a81a-a034-4f0c-8f3b-252b164d85f3
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

严重

**【描述】**

如果安全函数中的destMax参数不正确，则可能导致缓冲区溢出，在某些情况下可以造成任意代码执行漏洞。

因此，必须正确设置安全函数中的destMax参数。

**【正确示例】**

```
##### 场景1：destMax参数是魔鬼数字。
- 修复示例：destMax参数不能是魔鬼数字，destMax参数应设置为destBuff操作范围的内存大小。

```c
#define BUFF_SIZE 100

char *src = ...
size_t srcLen = ...
errno_t ret;
...

char destBuff1[BUFF_SIZE];
ret = memcpy_s(destBuff1, BUFF_SIZE, src, srcLen);          // 符合
ret = memcpy_s(destBuff1, sizeof(destBuff1), src, srcLen);  // 符合

unsigned char *destBuff2 = (unsigned char *)malloc(BUFF_SIZE);
...
ret = memcpy_s(destBuff2, BUFF_SIZE, src, srcLen);          // 符合
```
##### 场景2：destBuff是动态分配的内存指针时，destMax参数设置不正确。
- 修复示例：如果destBuff是动态分配的内存指针，那destMax应设置为分配时的内存大小。

```c
#define BUFF_SIZE 100
...
unsigned char *destBuff = (unsigned char *)malloc(BUFF_SIZE);
if (destBuff == NULL) {
    ... // 错误处理
}
...
unsigned char *src = ...
size_t srcLen = ...

errno_t ret = memcpy_s(destBuff, BUFF_SIZE, src, srcLen); // 符合
```
##### 场景3：destBuff是struct结构类型的单一对象的地址时，destMax参数设置不正确。
- 修复示例：如果destBuff是struct结构类型的单一对象的地址，那destMax应设置为struct结构类型的内存大小。

```c
typedef struct {
    int a;
    int b;
    int c;
} SomeStru;
...
SomeStru destBuff;
unsigned char *src = ...
size_t srcLen = ...

errno_t ret = memcpy_s(&destBuff, sizeof(SomeStru), src, srcLen);  // 符合
```

```
**【错误示例】**

```
##### 场景1：destMax参数是魔鬼数字。
- 错误示例：

```c
#define BUFF_SIZE 100

char *src = ...
size_t srcLen = ...
errno_t ret;
...

char destBuff1[BUFF_SIZE];
ret = memcpy_s(destBuff1, 100, src, srcLen);    // 不符合：魔鬼数字100

unsigned char *destBuff2 = (unsigned char *)malloc(BUFF_SIZE);
...
ret = memcpy_s(destBuff2, 100, src, srcLen);    // 不符合：魔鬼数字100
```
##### 场景2：destBuff是动态分配的内存指针时，destMax参数设置不正确。
- 错误示例：

```c
#define BUFF_SIZE 100
...
unsigned char *destBuff = (unsigned char *)malloc(BUFF_SIZE);
if (destBuff == NULL) {
    ... // 错误处理
}
...
unsigned char *src = ...
size_t srcLen = ...

errno_t ret = memcpy_s(destBuff, srcLen, src, srcLen);    // 不符合：destMax参数是srcLen，和destBuff无关
```
##### 场景3：destBuff是struct结构类型的单一对象的地址时，destMax参数设置不正确。
- 错误示例：

```c
typedef struct {
    int a;
    int b;
    int c;
} SomeStru;
...
SomeStru destBuff;
unsigned char *src = ...
size_t srcLen = ...

errno_t ret = memcpy_s(&destBuff, srcLen, src, srcLen); // 不符合：destMax参数是srcLen，和destBuff无关
```

```
**【修复建议】**

必须正确设置安全函数中的destMax参数。

1. destMax参数不能是魔鬼数字。

2. destMax参数应设置为destBuff操作范围的内存大小。

2.1 如果destBuff是固定长度的数组，那destMax应设置为数组的内存大小。

2.2 如果destBuff是动态分配的内存指针，那destMax应设置为分配时的内存大小。

3.3 如果destBuff是struct结构类型的单一对象的地址，那destMax应设置为struct结构类型的内存大小。
