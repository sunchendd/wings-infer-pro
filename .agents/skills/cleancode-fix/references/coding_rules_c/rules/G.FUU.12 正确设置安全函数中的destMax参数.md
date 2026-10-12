# G.FUU.12 正确设置安全函数中的destMax参数

- **规则ID**：f793617e-cd7b-4b47-8b97-9c62c2159ae4
- **更新时间**：2026-04-07 04:10:05

---

**【问题级别】**

严重

**【描述】**

安全函数的destMax参数设置应当准确，有效。





**【正确示例】**

```
1.1 使用时，destMax必须设置为 sizeof(destBuff) 或 BUFF_SIZE
#define BUFF_SIZE 100
...
char destBuff[BUFF_SIZE];
char *src = ...
size_t srcLen = ...
char strDest[BUFF_SIZE];
...
memcpy_s(destBuff, sizeof(destBuff), src, srcLen);   // 符合
memcpy_s(destBuff, BUFF_SIZE, src, srcLen);          // 符合
sprintf_s(strDest, sizeof(strDest), "Hello, world"); // 符合
...
memset_s(strDest, BUFF_SIZE, 0, BUFF_SIZE);          // 符合
scanf_s("%s", strDest, sizeof(strDest));             // 符合

1.2 如果 destBuff 作为参数跨函数传递，必须将 destBuff 的实际大小作为参数进行传递
#define BUFF_SIZE 100

int Foo(void)
{
    char destBuff[BUFF_SIZE];
    ...
    ParseBuff(destBuff, BUFF_SIZE); // 符合：传递BUFF_SIZE
    ...
}

int ParseBuff(char *destBuff, size_t destMax)
{
    char *src = ...
    size_t srcLen = ...
    memcpy_s(destBuff, destMax, src, srcLen);   // 符合
    ...
}

```
**【错误示例】**

```
以下代码，destBuff跨越到不可访问内存，属于误用：

#define BUFF_SIZE 100
...
char destBuff[BUFF_SIZE];
char *src = ...
size_t srcLen = ...
memcpy_s(destBuff, 0x7fffffff, src, srcLen); // 不符合
destMax参数设置原则

（为聚焦于说明destMax的用法，示例代码中省略了安全函数的返回值检查以及其他检查）

1. destBuff 为 char destBuff[BUFF_SIZE] 形式的局部变量的情况

1.1 使用时，destMax必须设置为 sizeof(destBuff) 或 BUFF_SIZE

#define BUFF_SIZE 100
...
char destBuff[BUFF_SIZE];
char *src = ...
size_t srcLen = ...
...
memcpy_s(destBuff, 100, src, srcLen);       // 不符合
memcpy_s(destBuff, srcLen, src, srcLen);    // 不符合

1.2 如果 destBuff 作为参数跨函数传递，必须将 destBuff 的实际大小作为参数进行传递
#define BUFF_SIZE 100

int Foo(void)
{
    char destBuff[BUFF_SIZE];
    ...
    ParseBuff(destBuff, 100);   // 不符合
    ParseBuff2(destBuff);       // 不符合：必须增加destMax参数
    ...
}

int ParseBuff(char *destBuff, size_t destMax)
{
    char *src = ...
    size_t srcLen = ...

    memcpy_s(destBuff, BUFF_SIZE, src, srcLen);        // 不符合
    memcpy_s(destBuff, sizeof(destBuff), src, srcLen); // 不符合
    memcpy_s(destBuff, 100, src, srcLen);              // 不符合
    memcpy_s(destBuff, srcLen, src, srcLen);           // 不符合
    ...
}

```
**【修复建议】**

参考规范http://openx.huawei.com/communityWikiDetails?communityId=41&ibid=SPE1000000103&navid=NVI1000001198
