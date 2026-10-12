# SecB_NullReturns

- **规则ID**：d4931125-34c2-42c5-9bbe-4b4dfc0c342f
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

可能返回null指针的函数，在使用前其返回值之前未判空。

**【正确示例】**

```


```
**【错误示例】**

```
/*
 * @scene malloc函数调用结果未判空，在sprintf_s中解引用
 */
void TestBad1()
{
    // returned_null: "malloc" returns "NULL" 
    // var_assigned: Assigning: "buf" = "NULL" return value from "malloc"
    char *buf = (char *)malloc(BUFFERSIZE);
    /* POTENTIAL FLAW: dereference: Dereferencing a pointer that might be "NULL" "buf" when calling "sprintf_s" */
    sprintf_s(buf, BUFFERSIZE, "hey");
    free(buf);
}

```
**【修复建议】**
