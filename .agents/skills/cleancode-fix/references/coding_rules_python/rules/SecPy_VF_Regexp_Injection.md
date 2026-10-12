# SecPy_VF_Regexp_Injection

- **规则ID**：9dc90956-b470-4028-95bc-17ac827f9ebc
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

ReDos攻击是正则编写不当导致的常见安全风险。Python语言的正则引擎本质上是非确定型有穷自动机（NFA），通过回溯机制尝试正则表达式的所有可能执行路径。NFA引擎采用回溯机制，回溯机制存在效率问题，在最坏的情况下，即使“注定”失败，依旧需要与所有可能的路径进行对比匹配，在确认所有可能路径都不匹配，才返回匹配失败。若直接使用外部输入数据进行正则匹配，攻击者可通过构造特殊的正则表达式或目标字符串触发“回溯陷阱”，造成拒绝服务，这种攻击方式称为正则表达式拒绝服务（ReDoS）。



本规则检测函数 re.search\re.match\re.find\re.findall 参数是否来自不可信输入，是则告警

**【正确示例】**

```
```
import re


def good_case():
    # 将正则表达式限定在白名单之内，可以通过合理设计白名单消除ReDos风险。
    pattern_string = input('请输入正则表达式：')
    # 白名单校验
    pattern_verify = verify(pattern_string)
    if pattern_verify:
        re.search(pattern_verify, 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!')


def verify(pattern_string):
    PATTERN = re.compile(r'\(.*[\*\+\|]+.*\)[\*\+]+')
    if PATTERN.search(pattern_string):
        return False
    else:
        return pattern_string
```

```
**【错误示例】**

```
```
import re

def regex_evaluate():
	# 直接将外部数据作为正则表达式和目标字符串进行匹配，存在ReDoS漏洞
	pattern_string = input('请输入正则表达式：')
	re.search(pattern_string, 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!')
```

```
**【修复建议】**

1）避免动态构建正则，若不可避免，则必须使用白名单或黑名单对外部数据进行校验和净化，保证最终构造出来的正则表达式中不存在Redos风险（即保证正则表达式中不存在重复分组）。

2）进行正则匹配前，先对匹配的文本的长度进行校验；
