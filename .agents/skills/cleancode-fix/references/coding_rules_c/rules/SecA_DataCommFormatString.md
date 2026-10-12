# SecA_DataCommFormatString

- **规则ID**：e69a0031-2e22-4f2c-8445-8cc02a799baf
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

调用格式化函数时，Format中参数的类型与个数必须与实际参数类型一致格式化函数中，Format中的参数类型与个数与实际参数不一致，会导致读写的数据与期望不一致， 造成输入输出数据错误，访问非法内存，写越界等问题。

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;格式化函数中，Format参数个数、类型应该要和实际参数个数、类型不一致告警
1、可变参数的前一个参数，不限制是const char*
2、适配了SSP的两个格式，"%_VSID"和 "%_T_4"【Example】&nbsp;&nbsp;//good example

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



//bad example

typedef struct AA{
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
