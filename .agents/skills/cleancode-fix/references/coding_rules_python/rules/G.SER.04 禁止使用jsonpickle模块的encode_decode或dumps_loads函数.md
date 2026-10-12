# G.SER.04 禁止使用jsonpickle模块的encode/decode或dumps/loads函数

- **规则ID**：aa233e77-4087-4c27-a042-7af9d8f7cfd3
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

严重

**【描述】**

jsonpickle模块支持将任意对象转化为json。



使用jsonpickle模块加载来源不可信的JSON字符串存在潜在的安全风险。 jsonpickle模块不会对输入进行校验，这导致攻击者可构造恶意输入获取执行权限。

**【正确示例】**

```


```
**【错误示例】**

```
import jsonpickle


poc = '{"py/reduce": [{"py/type": "subprocess.Popen"}, {"py/tuple": [{"py/tuple": ["cmd.exe", "/c", "calc.exe"]}]}]}'
# 成功启动计算器
jsonpickle.decode(poc)

```
**【修复建议】**

使用其它安全的序列化模块，否则就要进行严格的白名单校验或黑名单过滤。
