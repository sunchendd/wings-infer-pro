# SecA_IncompatibleCast

- **规则ID**：42964012-38cb-4ee8-8406-9228c19b8b18
- **更新时间**：2025-03-25 19:23:54

---

**【问题级别】**

严重

**【描述】**

不同类型的对象指针之间不能进行强制转换

**【正确示例】**

```
void GoodCase06()
{
    unsigned char arr[100] = { 0 };
    unsigned char *p = &arr[0];
 /* POTENTIAL FLAW GOOD: */
    strncat((char*)p, "dd", 3);
}

```
**【错误示例】**

```
void Func(void) 
{
    char c = 'x';
    int *ip = (int *)&c;  /* 不兼容的转换 */
    char *cp = (char *)ip;

    ASSERT(cp == &c); /* 在一些系统下会失败 */
}

```
**【修复建议】**

不同类型的对象指针之间不应进行强制转换
