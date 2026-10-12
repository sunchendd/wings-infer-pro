# G.FUU.20 使用库函数时避免竞争条件

- **规则ID**：9a659290-8835-44a0-bee2-31efae04066c
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

由于getenv为不可重入函数，连续调用getenv时，后一次对getenv的调用可能会覆盖上一次取到的字符串内容，导出程序执行异常。



因此，将getenv每次返回的数据先保存再使用。

**【正确示例】**

```
##### 场景1：多个线程调用getenv函数可能造成竞争条件问题。
- 修复示例：将getenv每次返回的数据先保存再使用。

```c
// 函数是将srcEnv复制一份。成功返回复制之后的首地址，失败返回NULL
char *TransEnv(const char *srcEnv)
{
    ... // 具体实现略。strcpy_s...
}

void Function(void)
{
    char *wxEnv = NULL;
    char *bdEnv = NULL;

    const char *envVal = getenv("TABLE_WX_ENV");
    if (envVal != NULL) {
        wxEnv = TransEnv(envVal);
        ... // 判断TransEnv函数返回值并正确处理异常
    } else {
        ... // 错误处理
        return;
    }

    envVal = getenv("TABLE_BD_ENV");
    if (envVal != NULL) {
        bdEnv = TransEnv(envVal);
        ... // 判断TransEnv函数返回值并正确处理异常
    } else {
        ... // 错误处理
        return;
    }

    // 符合：比较两个副本
    if (strcmp(wxEnv, bdEnv) == 0) {
        printf("They are the same.
");
    } else {
        printf("They are NOT the same.
");
    }

    ... // 退出前清理资源
}
```


```
**【错误示例】**

```
##### 场景1：多个线程调用getenv函数可能造成竞争条件问题。
- 错误示例：

```c
void Foo(void)
{
    char *wxEnv = NULL;
    char *bdEnv = NULL;

    wxEnv = getenv("TABLE_WX_ENV");
    if (wxEnv == NULL) {
        ... // 错误处理
        return;
    }

    bdEnv = getenv("TABLE_BD_ENV");
    if (bdEnv == NULL) {
        ... // 错误处理
        return;
    }

    // 不符合：由于getenv()是不可重入的，在第二次调用该函数时，可能会覆盖上一次取到的字符串内容，所以即使两个环境变量是不同的，但是最终两者wxEnv和bdEnv在比较时可能相同
    if (strcmp(wxEnv, bdEnv) == 0) {
        printf("They are the same.
");
    } else {
        printf("They are NOT the same.
");
    }
}
```


```
**【修复建议】**

将getenv每次返回的数据先保存再使用。
