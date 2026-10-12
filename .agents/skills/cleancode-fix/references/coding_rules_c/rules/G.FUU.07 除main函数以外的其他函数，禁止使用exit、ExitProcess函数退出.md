# G.FUU.07 除main函数以外的其他函数，禁止使用exit、ExitProcess函数退出

- **规则ID**：57fe241f-5565-48ce-87b4-39942c76a893
- **更新时间**：2026-04-07 04:10:05

---

**【问题级别】**

一般

**【描述】**

除了main函数以外，禁止任何地方调用exit、ExitProcess函数退出进程。直接退出进程可能会导致代码的复用性降低，某些资源（尤其是不属于进程的系统资源）在程序退出前难以得到有效地清理。



处理程序退出时必须通过不断返回上一层函数来终止运行。对于所有退出处理程序来说，能够正确执行它们的清理操作是很重要的，在安全性上可能很关键。

**【正确示例】**

```
bool LoadFile(const char *filePath)
{
    ASSERT(filePath != NULL);

    bool ret = false;
    FILE *fp = fopen(filePath, "rt");
    if (fp == NULL) {
        ... // 错误处理
        return ret;
    }
    ...

    return ret;
}

```
**【错误示例】**

```
void LoadFile(const char *filePath)
{
    ASSERT(filePath != NULL);

    FILE *fp = fopen(filePath, "rt");
    if (fp == NULL) {
        exit(0); // 不符合
    }

    ...
}

```
**【修复建议】**

禁用exit、ExitProcess函数（main函数除外）
