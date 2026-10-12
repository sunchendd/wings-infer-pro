# Forbid_Hard-coded_AK_Credentials

- **规则ID**：2c20eb75-e682-4450-97a6-dc9f93fd154f
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

硬编码的AccessKey机密可能会被滥用以获取隐私数据。

**【正确示例】**

```


```
**【错误示例】**

```
def bad():
    aws_id = "AKIEHI385HKH1IWUQEEN"
    return aws_id

```
**【修复建议】**
