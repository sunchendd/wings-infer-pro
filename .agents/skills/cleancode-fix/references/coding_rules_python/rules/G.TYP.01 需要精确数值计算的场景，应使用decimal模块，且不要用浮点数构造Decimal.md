# G.TYP.01 需要精确数值计算的场景，应使用decimal模块，且不要用浮点数构造Decimal

- **规则ID**：408401fb-7980-46ec-b275-aed037cf0912
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

一般

**【描述】**

在需要精确数值计算的情况下，使用浮点数不仅无法得到精确的计算结果，而且会导致程序出现意想不到的结果。

**【正确示例】**

```
### 场景1：浮点数使用
- 修复示例：使用Decimal模块，使用字符串格式的数值构造`Decimal`
```python
from decimal import Decimal


print(Decimal('12.3') * Decimal('0.1'))  # 符合，输出1.23
print(Decimal('3.14'))  # 符合，输出3.14
```
- 修复示例：使用Decimal模块，使用字符串格式的数值构造`Decimal`
```python
from decimal import Decimal


print(Decimal('6') / Decimal('3.14'))  # 符合
print(Decimal(1) / Decimal(7))  # 符合
print(Decimal('1') / Decimal('7'))  # 符合
```

```
**【错误示例】**

```
### 场景1：浮点数使用
- 错误示例：使用浮点数无法得到精确的计算结果
```python
print(12.3 * 0.1)  # 不符合，输出1.2300000000000002
print('{0:.20f}'.format(3.14))  # 不符合，输出3.14000000000000012434
```
- 错误示例：使用浮点数构造`Decimal`
```python
Decimal.from_float(12.222)   # 不符合
Decimal(3.14).adjusted()  # 不符合
print(Decimal(6) / Decimal(3.14))   # 不符合
```

```
**【修复建议】**

涉及精确的数值计算（货币、金融等），建议使用decimal模块。且不要用浮点数构造`Decimal`，应该使用字符串格式的数值构造`Decimal`。
