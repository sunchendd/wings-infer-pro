# G.SER.01 禁止使用pickle.load、_pickle.load和shelve模块加载外部数据

- **规则ID**：882c44de-b619-4aae-9462-c21b67ded7d3
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

使用pickle.load、_pickle.load和shelve模块加载外部数据存在安全风险。这些模块可以将Python对象序列化为二进制数据，然后将其保存到文件中。但是，如果不小心加载了恶意的二进制数据，就可能导致代码执行任意命令，从而造成安全漏洞。

如果需要加载外部数据，可以使用更安全的方式，比如json。

**【正确示例】**

```
##### 场景1：
- 修复示例：使用json加载外部数据

```python
import json


with open('data.json', 'r') as f:
    # 使用json.loads加载外部数据
    data = json.loads(f.read())  # 符合
```

```
**【错误示例】**

```
##### 场景1：
- 错误示例：使用pickle加载外部数据

```python
import pickle


with open('data.pkl', 'rb') as f:
    # 使用pickle.loads加载外部数据
    data = pickle.loads(f.read())  # 不符合
```

```
**【修复建议】**

1. 采用更为安全的序列化格式（例如json）处理不受信任的数据。

2. 使用hmac对序列化数据进行签名，确保数据没有被篡改。
