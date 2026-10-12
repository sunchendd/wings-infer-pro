# SecA_CSI_NullReturnUvp

- **规则ID**：441ec89b-ba43-42dd-b2fc-1cdbb1ae6369
- **更新时间**：2025-03-25 19:23:45

---

**【问题级别】**

一般

**【描述】**

检查kmalloc等内存分配函数是否对返回值进行了判空

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;匹配kmalloc类函数并记录返回值，在条件语句中校验是否有对该返回值校验，若没有则在路径分支结束的地方告警【Example】&nbsp;&nbsp;//good example

void testcase_good_01()
{
 char* p2;
 p2 = (char*)malloc(1);
 if(p2 == 0)
 {
  return;  
 }
}



//bad example

void testcase_bad_01()
{
 char* p1;
 p1 = (char*)malloc(1);
}

```
**【修复建议】**

确保对kmalloc等内存分配函数的返回值进行了判空
