# G.MEM.02 内存分配后必须判断是否成功

- **规则ID**：cab6d889-4158-44db-8dea-472d4f09905f
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

内存分配一旦失败，那么后续的操作会导致程序产生未定义行为的风险。比如malloc申请失败返回了空指针，对空指针的解引用会导致程序产生未定义行为。



内存申请函数返回的指针变量未判空场景，包括局部变量，成员变量，全局变量等。内存申请操作包括malloc、kmalloc等。

**【正确示例】**

```
##### 场景1：使用malloc函数返回未判空。
- 修复示例：
```c
void NotCheckMemoryAllocRetcase01Good01()
{
    char *tmp = (char *)malloc(sizeof(char) * NUM);
    /* 符合: 内存申请之后立刻判断是否成功 */
    if (tmp != NULL) {
        for (int i = 0; i < NUM; i++) {
            tmp[i] = 0;
        }
        free(tmp);
    }
}
```
##### 场景2：全局变量申请内存未判空。
- 修复示例：
```c
struct Flts {
    unsigned char uc1;
    unsigned char uc2;
    unsigned short us;
    unsigned char arr[100];
} Fts;

extern void *VOSMemAlloc(int h, int uc, int size);
extern void VOSMemFree(void *p);
Flts *gf1 = NULL;
Flts *gf2 = NULL;

void NotCheckGlobalMemoryAllocRetcase01Good01(int size)
{
    gf1 = (Flts *)VOSMemAlloc(1, 1, size);
    if (gf1 == NULL) {
        return;
    }
    gf2 = (Flts *)VOSMemAlloc(1, 1, size);
    /* 符合:  */
    if (gf2 == NULL) {
        VOSMemFree(gf1);
        gf1 = NULL;
        return;
    }
}
```


```
**【错误示例】**

```
##### 场景1：使用malloc函数返回未判空。
- 错误示例：
```c
void NotCheckMemoryAllocRetcase01Bad01()
{
    /* 申请内存 */
    char *tmp = (char *)malloc(sizeof(char) * NUM);
    for (int i = 0; i < NUM; i++) {
        tmp[i] = 0;
    }
    free(tmp);
    /* 不符合: 内存申请之后未判断是否成功 */
}
```
##### 场景2：全局变量申请内存未判空。
- 错误示例：
```c
struct Flts {
    unsigned char uc1;
    unsigned char uc2;
    unsigned short us;
    unsigned char arr[100];
} Fts;

extern void *VOSMemAlloc(int h, int uc, int size);
extern void VOSMemFree(void *p);
Flts *gf1 = NULL;
Flts *gf2 = NULL;

void NotCheckGlobalMemoryAllocRetcase01Bad01(int size)
{
    gf1 = (Flts *)VOSMemAlloc(1, 1, size);
    gf2 = (Flts *)VOSMemAlloc(1, 1, size);
    if (gf1 == NULL) {
        /* 不符合: gf2未判空，需要在模型中打开"report_global"选项才能告警 */
        return;
    }
}
```


```
**【修复建议】**

申请内存之后立即判空，防止后续有解引用空指针场景。
