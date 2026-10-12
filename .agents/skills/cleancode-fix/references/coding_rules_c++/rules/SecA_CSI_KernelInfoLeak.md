# SecA_CSI_KernelInfoLeak

- **规则ID**：c8beec4e-aa69-43e2-8dbc-865a39fb4a20
- **更新时间**：2025-03-25 19:23:44

---

**【问题级别】**

一般

**【描述】**

copy_to_user函数第二个参数未初始化，导致内核信息泄露

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;匹配copy_to_user函数，获取其第二个参数，并校验是否初始化【Example】&nbsp;&nbsp;//good example

void testcase_good_01(char* to)
{
 char from[5] = {0,1,2,3,4};
 copy_to_user(to,from,5); 
}



//bad example

void testcase_bad_01(char* to)
{
 char from[5];
 copy_to_user(to,from,5);
}

```
**【修复建议】**

使用copy_to_user函数时，确保其第二个参数经过初始化
