# SecPy_VF_Memcached_Injection

- **规则ID**：02ad67f2-12d2-4530-b11f-8ff4d0718b64
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

Memcached注入是一种攻击技术，攻击者通过构造恶意数据，将其存储到Memcached缓存中，并在后续的请求中对其进行利用，从而实现攻击目的。这种攻击方式可以导致数据泄露、数据篡改、拒绝服务等安全问题。

**【正确示例】**

```
```
import re
import pylibmc


def verify(data):
    data = data.replace(' ', '').replace('
', '').replace('\r', '').replace('0x0a', '').replace('0x0d', '').replace(
        '0x20', '')
    # 检测逻辑自定义，建议使用白名单校验，如：
    if re.match(r'^[a-zA-Z0-9_]+$', data):
        return data


def good_case():
    client = pylibmc.Client([host], binary=True)
    key = input()
    value = input()
    key_verify = verify(key)
    value_verify = verify(value)
    if key_verify and value_verify:
        client.set(key_verify, value_verify)
```

```
**【错误示例】**

```
```
import pylibmc

client = pylibmc.Client([host], binary=True)
key = input()
value = input()
client.set(key, value)
```

```
**【修复建议】**

不允许用户直接控制Memcached键/值对。如果必须允许则需对用户输入通过白名单的方式校验，仅允许输入指定字符
