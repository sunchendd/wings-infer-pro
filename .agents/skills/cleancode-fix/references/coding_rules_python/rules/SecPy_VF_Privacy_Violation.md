# SecPy_VF_Privacy_Violation

- **规则ID**：20d0084c-ec42-4713-85a3-1ecf8bf64a26
- **更新时间**：2025-06-05 04:15:02

---

**【问题级别】**

严重

**【描述】**

检测隐私泄露问题，对机密信息（如客户密码或社会保障号码）处理不当会危及用户的个人隐私。覆盖场景与fortify强制规则 Privacy Violation 相同

**【正确示例】**

```
import pprint

company = {
    "Apple":    {"founder": "Steven Jobs", "prodctions":["IPhone", "Mac"]},
    "MicroSoft":{"founder": "Bill Gates", "prodctions": ["Windows", "Office","Xbox"]},
}
# 打印非外部数据
pprint.pprint(company)

```
**【错误示例】**

```
import pprint
def bad_case():
  company = input()
  # 打印非外部数据
  pprint.pprint(company)

```
**【修复建议】**

传入外部数据之前需要对其进行校验
