# G.MEM.05 不要访问已释放的内存

- **规则ID**：6d766642-b6e3-4ad1-bae0-5a36c837e731
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

对已经释放的指针继续使用，则产生告警

**【正确示例】**

```
```
#include "stdlib.h" 

void foo()
{
    int* a = (int*)malloc(sizeof(int));
    free(a);
}
```

```
**【错误示例】**

```
```
#include "stdlib.h" 

void foo()
{
    int* a = (int*)malloc(sizeof(int));
    free(a);
    free(a);
}
```

```
**【修复建议】**

指针指向的内存被释放后，将该指针设置为空
