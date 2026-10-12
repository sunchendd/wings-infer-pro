# SecA_UnsignedCompareZero

- **规则ID**：615d26b7-4da7-49aa-90f3-5ffc26880faa
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

检测是否有对无符号类型变量进行无意义比较，如果有则告警

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;如果有对无符号整型变量或表达式与0进行无意义比较，如uintVal < 0、0 > uintVal、uintVal <= 0、 0 >= uintVal、 uintVal >= 0、0 <= uintVal，则告警
【Example】&nbsp;&nbsp;//good example

unsigned int ui = XXX;
 if (ui == 0);//good case
 if (0 == ui);//good case
 if (ui != 0);//good case
 if (0 != ui);//good case
 if (ui > 0);//good case
 if (0 < ui);//good case



//bad example

unsigned int ui = XXX;
if (ui < 0);//bad case
 if (0 > ui);//bad case
 if (ui >= 0);//bad case
 if (0 <= ui);//bad case
 if (ui <= 0);//bad case
 if (0 >= ui);//bad case

```
**【修复建议】**

无符号整型变量与0不要进行无意义比较
