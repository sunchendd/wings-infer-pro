# SecPy_VF_Insecure_Randomness

- **规则ID**：7e17b20e-be8e-4be2-b747-356de05834bb
- **更新时间**：2025-06-05 04:15:02

---

**【问题级别】**

严重

**【描述】**

检测不安全的随机数，生成了随机或伪随机值并传递了种子的函数不应使用受污染参数进行调用。覆盖场景与fortify规则 Insecure Randomness 相同

**【正确示例】**

```
import random
def good():
    random.seed(1)
    print('随机数：',random.random())

```
**【错误示例】**

```
import random
def bad():
    a = input()
    # POTENTIAL FLAW
    random.seed(a)
    print('随机数：',random.random())

```
**【修复建议】**

传入外部数据之前需要对其进行校验
