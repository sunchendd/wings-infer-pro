# SecA_IncompatibleCast

- **规则ID**：077a01aa-7499-4646-af56-3f5cee1d568a
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

严重

**【描述】**

不同类型的对象指针之间不能进行强制转换

**【正确示例】**

```
```
void GoodCase06()
{
    unsigned char arr[100] = { 0 };
    unsigned char *p = &arr[0];
 /* 符合: */
    strncat((char*)p, "dd", 4);
}
```

```
**【错误示例】**

```
```
void Func(void) 
{
    char c = 'x';
    int *ip = (int *)&c;  /* 不兼容的转换 */
    char *cp = (char *)ip;

    ASSERT(cp == &c); /* 在一些系统下会失败 */
}
```

```
**【修复建议】**

不同类型数据转换前要进行校验，确保符合程序逻辑。
