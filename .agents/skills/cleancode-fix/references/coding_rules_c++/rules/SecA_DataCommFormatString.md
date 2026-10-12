# SecA_DataCommFormatString

- **规则ID**：969714c2-f802-48de-80ae-41f6787e0f7b
- **更新时间**：2025-03-25 19:23:50

---

**【问题级别】**

一般

**【描述】**

调用格式化函数时，Format中参数的类型与个数必须与实际参数类型一致格式化函数中，Format中的参数类型与个数与实际参数不一致，会导致读写的数据与期望不一致， 造成输入输出数据错误，访问非法内存，写越界等问题。

**【正确示例】**

```
typedef struct AA{
 int ma;
 char mb;
}AA;

void good(char arg,char *p)
{
 char s[100];
 AA aa = {0};
    char a1[] = "kk";
 char a2[] = "ff";
 
 sprintf(s, "%s%s",a1, a2);//ok
}

```
**【错误示例】**

```
已填写typedef struct AA{
 int ma;
 char mb;
}AA;

void bad(char arg,char *p)
{
 char s[100];
 AA aa = {0};
    char a1[] = "kk";
 char a2[] = "ff";
 
 sprintf(s, "%s%s",a1);//error
}

```
**【修复建议】**

确保format函数参数个数和实际参数个数一致。
