# SecA_FormatStringTypeView

- **规则ID**：d6a830a0-1d78-4bb4-a527-27e7e420f177
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

检查format函数格式化符号和实际类型不匹配的场景

**【正确示例】**

```
void good()
{
 char s[100];
 int ulYear = 0, ulMonth = 0, ulDay = 0;
 
 sscanf_s(s, ""%u-%u-%u%*s"", &ulYear, &ulMonth, &ulDay);//ok
}

```
**【错误示例】**

```
void bad()
{
 char s[100];
 int ulYear = 0, ulMonth = 0, ulDay = 0;

 sscanf_s(s, "%u-%u-%u%s", &ulYear, &ulMonth, &ulDay);//error
}

```
**【修复建议】**

格式化输入输出函数的格式化标示符和参数类型应该一致

可参考华为安全函数库说明【格式化输出说明符】和【格式化输入说明符】
