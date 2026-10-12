# G.FUU.04 禁用atexit函数

- **规则ID**：17f1b6ba-d646-47de-83da-1b1879405d66
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

使用atexit()有可能导致资源没有被正确的清理：通过atexit()注册的函数须通过return返回，不应调用退出函数（如exit()）或者调用longjmp()等方式返回，否则这些注册函数可能得不到正确执行，还会导致程序产生未定义行为。同时对于所有的退出处理程序来说，程序员应该主动清理不再使用的资源，而不应该在最终程序退出后通过使用atexit()调用事先注册的函数被动地清理资源。

**【正确示例】**

```
重构代码，禁止使用atexit()函数

...
void ProcessExit(void)
{
    if (g_someResource == 0) {
        ... // g_someResource，在这里清理程序资源，代码省略
    }

    return;
}

int main(void)
{
    ...

    // main函数退出
    ProcessExit(); // 符合：主动调用资源清理函数
    return 0;
}

```
**【错误示例】**

```
在如下代码示例中，ProcessExit()函数由atexit()事先注册，在程序终止时执行必要的资源清理操作。但是如果g_someResource条件为真，则exit()被第二次调用，造成程序产生未定义行为。

...
int g_someResource = 1;

void ProcessExit(void)
{
    if (g_someResource == 0) {
        ... // g_someResource，在这里清理程序资源，代码省略

        exit(0); // 不符合：在本例程中调用exit，导致程序产生未定义行为
    }

    return;
}

int main(void)
{
    // 不符合：注册atexit()例程ProcessExit()，清理资源
    if (atexit(ProcessExit) != 0) {
        ... // 错误处理
    }

    ...

    // main函数退出
    return 0;
}

```
**【修复建议】**

参考规范http://openx.huawei.com/communityWikiDetails?communityId=41&ibid=SPE1000000103&navid=NVI1000001188
