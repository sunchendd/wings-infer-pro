# SecPy_DF_Sensitive_Info_Check

- **规则ID**：8969bee9-0cf6-46c9-aea6-cac63de0635a
- **更新时间**：2025-06-05 04:15:01

---

**【问题级别】**

严重

**【描述】**

敏感信息检查，检查的敏感信息分类包括：IP、URL、密码、弱加密算法、不安全协议等。

**【正确示例】**

```
def good():
    X = 1
    # POTENTIAL FLAW GOOD:
    print(' Please print the number:' + X)

```
**【错误示例】**

```
def bad1():
    # 姓名：name
    print('name:'+'sunny')

def bad2():
    # 工号：number
    print('number:'+'14578')

def bad3():
    # 部门：department
    print('department:'+'cloud BU')

def bad4():
    # 部门：ITDepartment
    print('ITDepartment :'+'cloud BU')

def bad5():
    # POTENTIAL FLAW: mailbox
    print('mailbox:'+'12345@huawei.com')

def bad6():
    # POTENTIAL FLAW
    cfg.StrOpt('weak_password', secret=True,default='abcd_123,Abcd_123,Huawei123,huawei_123,Huawei_123,admin_123,Admin123,Password123,password_123,Password_123')

```
**【修复建议】**

传入外部数据之前需要对其进行校验
