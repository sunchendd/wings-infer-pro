# SecA_HERT_AllocReturn

- **规则ID**：171f2604-fcf3-47ac-bee9-cd6401b2981d
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

内存申请函数的返回值必须判空，CODEX扫描规则HW_CSPL_C_ALLOC_RETURN_CHECK只包含了一些标准的申请内存的函数，未包含我们代码中的申请内存函数：CFG_StaticMemAlloc  LOGCORE_Malloc 等

**【正确示例】**

```
void test_good2(STU *stu)
{
 if(stu == NULL)
  return;
 
 stu->name = (char*)malloc(20);
 
 if(stu->name != NULL){
  func(stu->name);
 }
}

void test_good3()
{
 char *p;
 if((p = (char*)malloc(10)) != NULL ){
  func(p);
 }
}

void test_good4()
{
    char *p;
 if (NULL == (p = (char *)malloc(20))){
  
 }
}

void test_good5(char *p4)
{
    char *p1, *p2, *p3;
 p1 = (char *)malloc(20);
 p2 = (char *)malloc(20);
 p3 = (char *)malloc(20);
 if ((NULL == p1) || (NULL == p2)|| (p3 == NULL)|| (p4 == NULL))
 {
  
 } 
}

void test_good6()
{
 char *p = (char *)malloc(20);
 if (p)
 {
  func(p);
 }
}

void test_good7()
{
 char *p = (char *)malloc(20);
 if (!p)
 {
  return;
 }
 func(p);
}

void test_good8(char *p3)
{
    char *p1, *p2;
 p1 = (char *)malloc(20);
 p2 = (char *)malloc(20);
 if (!p1 || !p2 || !p3)
 {
  /* do something */
 }
}

void test_good9()
{
    char *p1, *p2;
 p1 = p2 = (char *)malloc(20);
 if (NULL == p1)
 {
  /* do something */
 }
}

void test_good10()
{
 char *p1;
 p1 = (char *)malloc(20, true);

}

void test_good11()
{
 char *p1;
 p1 = (char *)(MALLOC(20));
 if (NULL == p1)
 {
  /* do something */
 }

}

```
**【错误示例】**

```
//#include <iostream>
#define NULL 0
#define size_t int
extern "C"
{
    void *malloc(size_t size);
}

void *malloc(size_t size, bool flag);

#define MALLOC(len) \
{\
 void *ret;\
 ret = malloc(len);\
 ret;\
}

typedef struct Stu{
 char *name;
 int age;
}STU;

void func(char *p);

char *g_str;

void test_bad1()
{
 char *p = (char*)malloc(10);

 func(p);
}

```
**【修复建议】**

内存申请函数时候后要对其返回值进行判断
