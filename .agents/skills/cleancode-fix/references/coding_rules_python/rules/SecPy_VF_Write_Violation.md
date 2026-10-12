# SecPy_VF_Write_Violation

- **规则ID**：6d1337e0-3048-4c94-b402-ff1a786862eb
- **更新时间**：2025-06-05 04:15:03

---

**【问题级别】**

严重

**【描述】**

检测是否直接保存外部数据

**【正确示例】**

```
def verify(data):
    if data == 'safe':
        return data.replace('
', '_').replace('\r', '_')
    else:
        ...
def good_case():
    data = input()
    data_verify = verify(data)
    f = open('', 'r')
    # POTENTIAL FLAW: 保存不可信数据前未进行转义
    f.write(data_verify)
    f.close()

```
**【错误示例】**

```
def bad_case():
    data = input()
    f = open('', 'r')
    # POTENTIAL FLAW: 保存不可信数据前未进行转义
    f.write(data)
    f.close()

```
**【修复建议】**

传入外部数据之前需要对其进行校验
