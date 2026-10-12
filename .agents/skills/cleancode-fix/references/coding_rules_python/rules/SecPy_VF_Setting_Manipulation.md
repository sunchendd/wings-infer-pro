# SecPy_VF_Setting_Manipulation

- **规则ID**：a98d004c-f635-452b-86a7-be9bf71a56ec
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

允许对系统设置进行外部控制可以导致服务中断或意外的应用程序行为。当攻击者能够通过控制某些值来监控系统的行为、管理特定的资源、或在某个方面影响应用程序的功能时，即表示发生了 Setting Manipulation 漏洞。

**【正确示例】**

```
```
import os


def good_case():
    if hasattr(os, 'unsetenv'):
        os.unsetenv('_MEIPASS2')  # 非外部数据
    else:
        os.putenv('_MEIPASS2', '')
```

```
**【错误示例】**

```
```
import os


def bad_case():
    # TAINT DATA
    a = input()
    # 不符合
    os.unsetenv(a)
```

```
**【修复建议】**

禁止用户控制系统配置。如果必须允许用户控制系统配置，则应该对用户的输入进行校验
