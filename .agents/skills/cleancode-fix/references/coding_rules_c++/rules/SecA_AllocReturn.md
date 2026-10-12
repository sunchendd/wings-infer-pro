# SecA_AllocReturn

- **规则ID**：967da1aa-b9d9-47b2-8359-e5eb133a842c
- **更新时间**：2025-03-25 19:23:27

---

**【问题级别】**

一般

**【描述】**

内存申请函数返回未判空告警。



**【正确示例】**

```
```cpp
#include <stdio.h>
#include <malloc.h>
#define MAX_LEN 20
void func(char *p) {
    //do something
    p[0] = 'a';
    p[1] = 'b';
}
void GoodCase()
{
    char *str = (char *)malloc(MAX_LEN);
	if(str != NULL){
		func(str);
        free(str);
	}
}
```


```
**【错误示例】**

```
```cpp
#include <stdio.h>
#include <malloc.h>
#define MAX_LEN 20
void func(char *p) {
    //do something
    p[0] = 'a';
    p[1] = 'b';
}
// true_negative SecBrella:SecA_AllocReturn
void BadCase()
{
    char *str = (char *)malloc(MAX_LEN);
    func(str);  // Defect here
    free(str);
}
```


```
**【修复建议】**

申请内存之后立即判空，防止后续有引用空指针场景。
