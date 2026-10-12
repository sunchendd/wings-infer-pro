# SecA_PackagedFree

- **规则ID**：81d10e33-5010-437c-b849-19836eb501dc
- **更新时间**：2025-03-25 19:23:57

---

**【问题级别】**

一般

**【描述】**

检查自定义内存释放函数并告警

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;检查以下释放函数（free，closesocket，VOS_MemFree，VOS_Free）的封装函数告警，包括多级封装。
例如A函数封装了free函数，A函数会告警；B函数封装了A函数，B函数也会告警。【Example】&nbsp;&nbsp;//good example

void xxFree(char *p)//封装函数
{
   free(p);
}

char *g = ...;//全局变量

void  good1{}
{  ........
    xxFree(g);
    g = NULL;//置空
}

void  good2{}
{
    ........
    xxFree(g);
     g = NULL; //置空
    .......
    xxFree(g);
     g = NULL;//置空
}



//bad example

void xxFree(char *p)//封装函数
{
   free(p);
}

char *g = ...;//全局变量

void  bad1{}
{  ........
    xxFree(g);
}//g未置空

void  bad2{}
{
    ........
    xxFree(g);
    .......
    xxFree(g);//g双重释放
}//g未置空

```
**【修复建议】**

调用封装的释放函数后，指针立即置空或赋予新值
