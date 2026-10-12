# SecA_FormatStringNumView

- **规则ID**：833a8111-816a-44e6-810e-bab9645bc778
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

检查格式化输入输出函数的格式化标示符和参数个数不一致告警

**【正确示例】**

```
void test_good01()
{
 char buffer[80];
 int ret = -1;
 ret = scanf_s(""%s"",buffer,sizeof(buffer));
}

```
**【错误示例】**

```
void test_bad01()
{
 char buffer[80];
 int ret = -1;
 /* POTENTIAL FLAW: 缓冲区长度参数大于缓冲区实际长度 */
 ret = scanf_s("%s",buffer,sizeof(buffer)+1);
}

```
**【修复建议】**

确保format函数参数个数和实际参数个数一致。
