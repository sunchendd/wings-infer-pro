# SecA_LSW_R_FuncRetPtr

- **规则ID**：40140b1e-1af1-4b2f-8ca7-7abaea1055c1
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

对函数返回值为指针，解引用前未判空的场景进行告警。

**【正确示例】**

```
void* fun(char* s)
{
 char c = 'a';
 if(*s == c)
 {
  return s;
 }
 return NULL;
}

void testcase_good_01(char* s)
{
 char* p;
 p = fun(s);
 if(p == NULL)
 {
  return;
 }
 char a = *p;
}


```
**【错误示例】**

```
void* fun(char* s)
{
 char c = 'a';
 if(*s == c)
 {
  return s;
 }
 return NULL;
}

void testcase_bad_01(char* s)
{
 char* q;
 q = fun(s);
 char a = *q;
}

```
**【修复建议】**

对函数返回值为指针，解引用前未判空的场景进行告警。
