# G.EDV.01 禁止使用eval和exec函数执行不可信代码

- **规则ID**：ab814711-c684-40b8-b22a-aed0f4329528
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

在使用eval和exec函数执行代码时，如果输入的代码来自不可信来源，例如用户输入的字符串或从网络上下载的代码，那么使用eval和exec函数执行代码就会存在安全问题。攻击者可以利用这些函数来执行恶意代码，如获取敏感信息、损坏系统或进行远程控制等。因此，为了保证程序的安全性，禁止在执行不可信代码时使用eval和exec函数。

**【正确示例】**

```
##### 场景1：
- 修复示例：对外部数据进行校验
```python
def string_verify(input_str):
    # 检查输入字符串的长度
    if not input_str or len(input_str) > 20:
        raise ValueError("输入字符串无效")
    # 删除或转义输入字符串中的特殊字符
    verified_str = input_str.replace("'", "").replace('"', "").replace("\\", "")
    return verified_str


code = input("请输入代码：")
# 校验外部数据
verified_code = string_verify(code)
eval(verified_code)  # 符合
```

```
**【错误示例】**

```
##### 场景1：
- 错误示例：直接使用外部数据执行eval函数
```python
code = input("请输入代码：")
# 直接使用外部数据执行eval函数
eval(code)  # 不符合
```

```
**【修复建议】**

对传入eval、exec等函数的不可信参数进行校验。
