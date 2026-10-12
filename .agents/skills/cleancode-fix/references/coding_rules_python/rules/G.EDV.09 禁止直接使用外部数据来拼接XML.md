# G.EDV.09 禁止直接使用外部数据来拼接XML

- **规则ID**：25249156-322d-4f71-a78b-6f7507767067
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

严重

**【描述】**

Python直接使用外部数据来拼接XML，可能存在安全风险，如果外部数据包含恶意代码或者SQL注入等，可能导致程序运行异常或者数据泄露等问题。例如，如果用户的输入中包含特殊字符（例如“<”、“>”、“&”、“’”、“"”等），攻击者可能会通过构造特定的输入来影响XML的结构和内容，从而引发攻击。一个典型的攻击场景是，攻击者可以通过控制XML文档修改电子商务中的认证凭据，或修改商品的价格，对商家造成经济损失。因此，禁止直接使用外部数据拼接XML，若无法避免，建议在拼接XML时采取一定的安全措施。

**【正确示例】**

```
##### 场景1：

- 修复示例1：白名单方式校验示例一（使用正则表达式）
```python
import xml.etree.ElementTree as ET
import re


def my_clean(input_str):
    # 白名单校验：使用正则表达式
    compile_pattern = re.compile('^\d+$')
    if compile_pattern.match(input_str):
        return input_str
    return '0'


root = ET.Element("root")
child = ET.Element("child")
amount = input()
# 校验外部数据
verified_amount = my_clean(amount)
child.text = '<order>' \
             '<item>laptop</item>' \
             '<price>2800.00</price>' \
             '<amount>' + verified_amount + '</amount>' \
             '</order>'
root.append(child)  # 符合
```

- 修复示例2：白名单方式校验示例二（使用字符串方法isdigit()判断字符串中是否只包含数字字符）
```python
import xml.etree.ElementTree as ET


def my_clean(input_str):
    # 白名单校验：判断字符串中是否只包含数字字符
    if input_str.isdigit():
        return input_str
    return '0'


root = ET.Element("root")
child = ET.Element("child")
amount = input()
# 校验外部数据
verified_amount = my_clean(amount)
child.text = '<order>' \
             '<item>laptop</item>' \
             '<price>2800.00</price>' \
             '<amount>' + verified_amount + '</amount>' \
             '</order>'
root.append(child)  # 符合
```

- 修复示例3：黑名单方式校验
```python
import xml.etree.ElementTree as ET
import re


def my_clean(input_str):
    # 黑名单校验：使用正则表达式
    compile_pattern = re.compile('[<>"\'＆]+')
    if compile_pattern.search(input_str):
        return '0'
    return input_str


root = ET.Element("root")
child = ET.Element("child")
amount = input()
# 校验外部数据
verified_amount = my_clean(amount)
child.text = '<order>' \
             '<item>laptop</item>' \
             '<price>2800.00</price>' \
             '<amount>' + verified_amount + '</amount>' \
             '</order>'
root.append(child)  # 符合
```


```
**【错误示例】**

```
##### 场景1：

- 错误示例：直接使用外部数据拼接XML

以下XML文档定义了电子商城中笔记本电脑的价格，同时接受外部数据修改笔记本电脑的数量
```python
import xml.etree.ElementTree as ET


root = ET.Element("root")
child = ET.Element("child")
amount = input()
# 直接使用外部数据拼接XML
child.text = '<order>' \
             '<item>laptop</item>' \
             '<price>2800.00</price>' \
             '<amount>' + amount + '</amount>' \
             '</order>'
root.append(child)  # 不符合
```
若输入为：
```python
1000</amount><item>laptop</item><price>28.00</price><amount>10000
```
则实际生成的XML文档为：
```python
<order>
	<item>laptop</item>
	<price>2800.00</price>
	<amount>1000</amount>
	<item>laptop</item>
	<price>28.00</price>
	<amount>10000</amount>
</order>
```
使用sax解析器解析上述XML文档时，第二个价格标签将覆盖第一个价格标签，第二个数量标签也将覆盖第一个数量标签，则最终仅花费28元就可购买到价值2800元的笔记本电脑。

```
**【修复建议】**

禁止直接使用外部数据拼接XML，若无法避免，则需对外部数据进行严格校验和净化；此外，建议使用defusedxml模块处理XML数据，详情可参考defusedxml官方文档。
