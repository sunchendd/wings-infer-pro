# 安全TOP问题-解引用空指针

- **规则ID**：a8e97320-1eef-46c4-a947-e00c03f20df9
- **更新时间**：2025-03-25 19:24:02

---

**【问题级别】**

严重

**【描述】**

空指针类规则。变量判空或者赋空之后（源点, source点），在为空的分支下直接解引用（告警点，sink点），规则告警。



**【正确示例】**

```
##### 场景1：在空分支下不对指针做解引用操作
```cpp
#include<stdio.h>
#include<stdlib.h>
#define INT_MAX 100
void GoodTest01(const int* str)
{
    if (str == NULL) {
        printf("str is NULL!
");
        return;
    } //异常分支，返回
    int c = *str; // 符合：指针非空
    printf("data is %d
", c);
}
int testGood()
{
    GoodTest01(NULL);
    int* p = (int*) malloc(INT_MAX);
    *p = 0;
    GoodTest01(p);
    return 0;
}
```
##### 场景2：指针释放后不做引用
```cpp
#include<stdio.h>
#include<stdlib.h>
#define INT_MAX 100
int testBad()
{
    int* pDev = (int*) malloc(sizeof(int));
    if (pDev == NULL) {
        return -1;
    }
    *pDev = 1;
    printf("*pDev = %d
", *pDev);
    free(pDev);
    printf("pDev is free!");
    return 0;
}
```


```
**【错误示例】**

```
##### 场景1：在空分支下对指针做解引用操作
```cpp
#include<stdio.h>
#include<stdlib.h>
#define INT_MAX 100
// true_negative SecBrella:SecB_ForwardNull
void BadTest01(const int* str)
{
    if (str == NULL) {
        //异常分支未返回
        printf("str is NULL!
");
    }
    int c = *str; //空指针直接解引用
    printf("data is %d
", c);
}
int main()
{
    BadTest01(NULL);
    int* p = (int*) malloc(INT_MAX);
    *p = 0;
    BadTest01(p);
    return 0;
}
```


```
**【修复建议】**

在空分支下不对指针做解引用操作
