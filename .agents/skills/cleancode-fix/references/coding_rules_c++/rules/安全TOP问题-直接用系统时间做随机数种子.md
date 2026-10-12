# 安全TOP问题-直接用系统时间做随机数种子

- **规则ID**：0a232124-d9d4-4846-abd4-83cf038f1269
- **更新时间**：2025-03-25 19:24:00

---

**【问题级别】**

一般

**【描述】**

系统时间设置随机值种子

**【正确示例】**

```
void test_good(int seed)
{
 VOS_SetSeed(seed);//非time
}

```
**【错误示例】**

```
【Instruction】1.安全的设置随机数种子函数：RAND_seed、CRYPT_randSeed、IPSI_CRYPT_rand_seed、VOS_RandSeed_Safe、VOS_SetSeed
2.系统时间函数：clock、difftime、mktime、time、asctime、ctime、gmtime、localtime、gettimeofday 、GetTickCount、timeGetTime、gettime
3.使用标记污点的方法，将系统时间函数的返回值和出参标记为taint，在调用随机函数时，检查种子是否被污染，被污染则告警。【Example】void test_bad()
{
     VOS_SetSeed(time(NULL));//error
}

```
**【修复建议】**

参照《安全及隐私保护设计检视Checklist_v3.0》对应子检查项D-CAS-4-5：禁止直接用系统时间做随机数种子。
