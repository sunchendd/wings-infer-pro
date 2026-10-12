# SecA_SnprintfMisuse

- **规则ID**：a75dcca9-553b-4dde-8f43-a7753c07b5a7
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

snprintf_s等等函数的destMax和count参数检查

**【正确示例】**

```
```
【Instruction】&nbsp;&nbsp;覆盖函数：snprintf_s、_snprintf_s、_snwprintf_s、vsnprintf_s、_vsnprintf_s、_vsnwprintf_s、VOS_vsnprintf_Safe、VOS_snprintf_s、VOS_vsnprintf_s
1、count>=destMax 告警
2、strDest是p+xx场景时，如果是p+常量，destMax >【p的长度-常量】告警；
如果是p+非常量，destMax是【p的长度-非常量】不告警，其他告警【Example】&nbsp;&nbsp;//good example

1、count>=destMax 告警
 char dest[10];
 int len = sizeof(dest);
 snprintf_s(dest,10,9,"%s%s", "ddd", "ddddd");//ok

2、strDest是p+xx场景时，如果是p+常量，destMax >【p的长度-常量】告警
 char dest[10] = "dd";
 snprintf_s(dest + 2,8,7,"%s%s", "ddd", "ddddd");//ok

3、strDest是p+非常量，destMax是【p的长度-非常量】不告警，其他告警；
 char dest[10] = "dd";
 snprintf_s(dest + strlen(dest),10-strlen(dest),10-strlen(dest)-1,"%s%s", "ddd", "ddddd");//ok
```

```
**【错误示例】**

```
```
1、count>=destMax 告警
 char dest[10];
 int len = sizeof(dest);
 snprintf_s(dest,10,11,"%s%s", "ddd", "ddddd");//error
 snprintf_s(dest,10,10,"%s%s", "ddd", "ddddd");//error
 snprintf_s(dest,len,len,"%s%s", "ddd", "ddddd");//error
 
2、strDest是p+xx场景时，如果是p+常量，destMax >【p的长度-常量】告警 
 char dest[10] = "dd";
 snprintf_s(dest + 2,11,9,"%s%s", "ddd", "ddddd");//error
 snprintf_s(&dest[2],10,9,"%s%s", "ddd", "ddddd");//error
  
3、strDest是p+非常量，destMax是【p的长度-非常量】不告警，其他告警；
 char dest[10] = "dd";
 snprintf_s(dest + strlen(dest),10,9,"%s%s", "ddd", "ddddd");//error
```

```
**【修复建议】**

destMax是目的缓冲区总大小，destMax 大于 count以保证有截断功能
